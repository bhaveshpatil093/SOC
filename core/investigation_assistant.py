"""
core/investigation_assistant.py

AI-powered SOC Investigation Assistant for ISRO SOC Analytics.

Operates exclusively on data already in Streamlit session_state —
no additional Elasticsearch queries are made.

Two operating modes:
  LLM Mode       — Routes to Google Gemini or OpenAI if an API key is
                   configured in .env (GEMINI_API_KEY / OPENAI_API_KEY).
  Fallback Mode  — Always available; generates structured, explainable
                   answers purely from the analytics already computed.

Routing priority: Gemini → OpenAI → Deterministic Fallback.
"""

from __future__ import annotations

import importlib.util
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import pandas as pd

from config import get_logger, settings

logger = get_logger(__name__)


# ─── Provider Enum ────────────────────────────────────────────────────────────

class LLMProvider(Enum):
    GEMINI = "gemini"
    OPENAI = "openai"
    NONE   = "none"


# ─── Typed Session Context ─────────────────────────────────────────────────────

@dataclass
class SessionContext:
    """
    Typed bundle of analytics data extracted from Streamlit session_state.

    All fields are optional — the assistant gracefully handles any combination
    of completed / not-yet-run analysis stages.
    """

    # ── Log batch ─────────────────────────────────────────────────────────────
    raw_hits:    List[Dict[str, Any]] = field(default_factory=list)
    total_hits:  int = 0

    # ── ML anomaly detection ──────────────────────────────────────────────────
    ml_scored_df: Optional[pd.DataFrame] = None
    ml_summary:   Optional[Dict[str, Any]] = None

    # ── Sigma detection ───────────────────────────────────────────────────────
    sigma_report: Optional[Any] = None   # DetectionReport (avoids circular import)
    sigma_rules:  List[Any]     = field(default_factory=list)

    # ── Unified threat scoring ────────────────────────────────────────────────
    threat_results: List[Any] = field(default_factory=list)  # List[ThreatContext]

    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def from_session_state(cls, state: Dict[str, Any]) -> "SessionContext":
        """Build a SessionContext from st.session_state (passed as a dict)."""
        raw_hits: List[Dict[str, Any]] = []
        lr_pages = state.get("lr_pages", {})
        for page in sorted(lr_pages.values(), key=lambda p: getattr(p, "page_num", 0)):
            raw_hits.extend(getattr(page, "hits", []))
            if len(raw_hits) >= 10_000:   # Memory safety cap
                raw_hits = raw_hits[:10_000]
                break

        return cls(
            raw_hits=raw_hits,
            total_hits=state.get("lr_total_hits", len(raw_hits)),
            ml_scored_df=state.get("ml_scored_df"),
            ml_summary=state.get("ml_summary"),
            sigma_report=state.get("sigma_report"),
            sigma_rules=state.get("sigma_rules", []),
            threat_results=state.get("threat_results", []),
        )

    # ── Convenience properties ────────────────────────────────────────────────

    @property
    def has_data(self) -> bool:
        return len(self.raw_hits) > 0

    @property
    def has_ml(self) -> bool:
        return self.ml_summary is not None

    @property
    def has_sigma(self) -> bool:
        return self.sigma_report is not None

    @property
    def has_threats(self) -> bool:
        return len(self.threat_results) > 0


# ─── Investigation Assistant ──────────────────────────────────────────────────

class InvestigationAssistant:
    """
    AI-powered SOC investigation assistant.

    Usage::

        ctx = SessionContext.from_session_state(dict(st.session_state))
        assistant = InvestigationAssistant(ctx)
        response = assistant.answer("Summarize suspicious activity")
    """

    def __init__(self, ctx: SessionContext) -> None:
        self.ctx = ctx
        self._provider: LLMProvider = self._detect_provider()
        self._context_text: str = self._build_context_summary()

    # ── Provider detection ────────────────────────────────────────────────────

    def _detect_provider(self) -> LLMProvider:
        if settings.gemini_api_key:
            if importlib.util.find_spec("google.generativeai") is not None:
                logger.info("AI Assistant: using Gemini (%s)", settings.gemini_model)
                return LLMProvider.GEMINI
            logger.info("GEMINI_API_KEY set but google-generativeai not installed — using fallback.")
        if settings.openai_api_key:
            if importlib.util.find_spec("openai") is not None:
                logger.info("AI Assistant: using OpenAI (%s)", settings.openai_model)
                return LLMProvider.OPENAI
            logger.info("OPENAI_API_KEY set but openai not installed — using fallback.")
        return LLMProvider.NONE

    @property
    def provider(self) -> LLMProvider:
        return self._provider

    @property
    def is_llm_mode(self) -> bool:
        return self._provider != LLMProvider.NONE

    # ── Context summary builder ───────────────────────────────────────────────

    def _build_context_summary(self) -> str:
        """
        Produce a compact (≤ ~1500 token) text snapshot of all session data.
        This is prepended to LLM requests and also shown in the UI.
        """
        ctx = self.ctx
        lines: List[str] = ["=== ISRO SOC Analytics — Session Context ===\n"]

        # ── Batch info ────────────────────────────────────────────────────────
        if ctx.has_data:
            lines.append(f"[LOG BATCH] {len(ctx.raw_hits):,} logs in memory "
                         f"(total matched: {ctx.total_hits:,})")

            # Infer time range from @timestamp
            ts_vals = [h.get("_source", {}).get("@timestamp", "")
                       for h in ctx.raw_hits[:200]]
            ts_vals = [t for t in ts_vals if t]
            if ts_vals:
                lines.append(f"  Time range: {min(ts_vals)[:19]} → {max(ts_vals)[:19]}")

            # Top entities
            src_ip_ct: Dict[str, int] = {}
            user_ct:   Dict[str, int] = {}
            host_ct:   Dict[str, int] = {}
            for h in ctx.raw_hits:
                s = h.get("_source", {})
                ip   = s.get("source", {}).get("ip")   or s.get("src_ip", "")
                user = s.get("user",   {}).get("name")  or s.get("user.name", "")
                host = s.get("host",   {}).get("name")  or s.get("host.name", "")
                if ip:   src_ip_ct[ip]  = src_ip_ct.get(ip, 0)  + 1
                if user: user_ct[user]   = user_ct.get(user, 0)   + 1
                if host: host_ct[host]   = host_ct.get(host, 0)   + 1

            def _top(d: Dict[str, int], n: int = 5) -> str:
                return ", ".join(f"{k}({v})" for k, v in
                                 sorted(d.items(), key=lambda x: x[1], reverse=True)[:n])

            if src_ip_ct: lines.append(f"  Top src IPs:  {_top(src_ip_ct)}")
            if user_ct:   lines.append(f"  Top users:    {_top(user_ct)}")
            if host_ct:   lines.append(f"  Top hosts:    {_top(host_ct)}")
        else:
            lines.append("[LOG BATCH] No logs loaded.")

        # ── ML summary ────────────────────────────────────────────────────────
        if ctx.has_ml:
            s = ctx.ml_summary  # type: ignore[assignment]
            lines.append(
                f"\n[ML ANOMALY] {s.get('n_anomalies', 0)} anomalies / {s.get('n_total', 0)} total "
                f"({s.get('anomaly_rate_pct', 0):.1f}% rate, "
                f"max score: {s.get('max_score', 0):.3f})"
            )
        else:
            lines.append("\n[ML ANOMALY] Not yet run.")

        # ── Sigma summary ─────────────────────────────────────────────────────
        if ctx.has_sigma:
            r = ctx.sigma_report
            lines.append(
                f"\n[SIGMA] {r.matched_hits} events matched | "
                f"{len(r.triggered_rules)} rules triggered | "
                f"{r.total_rule_triggers} total triggers"
            )
            if r.triggered_rules:
                top3 = sorted(r.triggered_rules,
                              key=lambda x: r.rule_trigger_counts.get(x.rule_id, 0),
                              reverse=True)[:3]
                lines.append("  Top rules: " + ", ".join(
                    f"{x.title}[{x.severity}]" for x in top3))
            if r.severity_distribution:
                sev = " | ".join(f"{k}:{v}" for k, v in r.severity_distribution.items())
                lines.append(f"  Severity: {sev}")
            if r.mitre_tactics:
                top_t = sorted(r.mitre_tactics.items(), key=lambda x: x[1], reverse=True)[:6]
                lines.append("  MITRE: " + ", ".join(f"{t}({n})" for t, n in top_t))
        else:
            lines.append("\n[SIGMA] Not yet run.")

        # ── Threat summary ────────────────────────────────────────────────────
        if ctx.has_threats:
            res = ctx.threat_results
            crit = sum(1 for r in res if r.risk_level == "Critical")
            high = sum(1 for r in res if r.risk_level == "High")
            med  = sum(1 for r in res if r.risk_level == "Medium")
            low  = sum(1 for r in res if r.risk_level == "Low")
            lines.append(
                f"\n[THREATS] {len(res)} scored alerts — "
                f"Critical:{crit} High:{high} Medium:{med} Low:{low}"
            )
            for t in res[:3]:
                if t.threat_score >= 40:
                    lines.append(f"  • [{t.risk_level} {t.threat_score}/100] "
                                 f"{t.timestamp[:19]}: {t.explanation[:120]}")
        else:
            lines.append("\n[THREATS] Not yet run.")

        return "\n".join(lines)

    # ── Public answer entry point ─────────────────────────────────────────────

    def answer(self, question: str) -> str:
        """
        Route a question to the best available engine.
        Always returns a non-empty string.
        """
        if not question.strip():
            return "Please ask me something about the current investigation."

        if self._provider == LLMProvider.GEMINI:
            try:
                return self._gemini_answer(question)
            except Exception as exc:
                logger.warning("Gemini call failed, falling back: %s", exc)

        if self._provider == LLMProvider.OPENAI:
            try:
                return self._openai_answer(question)
            except Exception as exc:
                logger.warning("OpenAI call failed, falling back: %s", exc)

        return self._fallback_answer(question)

    # ── LLM backends ─────────────────────────────────────────────────────────

    def _system_prompt(self) -> str:
        return (
            "You are an expert SOC (Security Operations Center) analyst assistant for "
            "ISRO SOC Analytics. Help security analysts investigate incidents, understand "
            "threat alerts, and interpret security analytics. Answer concisely in plain "
            "security analyst language. Focus only on what you know from the provided "
            "context. If a question cannot be answered from the context, say so clearly.\n\n"
            + self._context_text
        )

    def _gemini_answer(self, question: str) -> str:
        import google.generativeai as genai  # type: ignore[import]
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            system_instruction=self._system_prompt(),
        )
        resp = model.generate_content(question)
        return resp.text.strip()

    def _openai_answer(self, question: str) -> str:
        from openai import OpenAI  # type: ignore[import]
        client = OpenAI(api_key=settings.openai_api_key)
        resp = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": self._system_prompt()},
                {"role": "user",   "content": question},
            ],
            max_tokens=800,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()

    # ── Deterministic fallback ────────────────────────────────────────────────

    def _fallback_answer(self, question: str) -> str:
        """Keyword-based intent dispatch — always available, no API needed."""
        q = question.lower()

        if any(k in q for k in ["summar", "overview", "what happened", "situation",
                                  "what's going on", "brief", "status"]):
            return self._answer_summary()

        if any(k in q for k in ["sigma", "rule", "signature", "detection rule", "match"]):
            return self._answer_sigma()

        if (any(k in q for k in ["anomal", "ml", "machine learn", "isolation", "outlier", "model"])
                and "threat" not in q):
            return self._answer_anomaly()

        if any(k in q for k in ["threat", "alert", "critical", "high risk", "risk", "danger",
                                  "score", "priorit"]):
            return self._answer_threats()

        if any(k in q for k in ["user", "who", "identity", "account", "login", "credential"]):
            return self._answer_entities("user")

        if any(k in q for k in ["host", "machine", "endpoint", "server", "computer", "device"]):
            return self._answer_entities("host")

        if any(k in q for k in [" ip", "network", "address", "src ip", "source ip", "destination",
                                  "traffic"]):
            return self._answer_entities("ip")

        if any(k in q for k in ["mitre", "att&ck", "tactic", "technique", "t1", "lateral",
                                  "exfil", "persist", "initial access"]):
            return self._answer_mitre()

        if any(k in q for k in ["explain", "why", "reason", "because", "what caused",
                                  "describe event", "tell me about"]):
            doc_id = self._extract_doc_id(question)
            return self._answer_explain_event(doc_id)

        if any(k in q for k in ["help", "what can you", "how do i", "capabilities",
                                  "what should", "next step", "recommend", "guide"]):
            return self._answer_help()

        return self._answer_general(question)

    # ── Intent handlers ───────────────────────────────────────────────────────

    def _answer_summary(self) -> str:
        ctx = self.ctx
        if not ctx.has_data:
            return (
                "## 📋 No Data Loaded\n\n"
                "To start an investigation:\n"
                "1. Go to **📥 Log Retrieval** and retrieve a batch of logs\n"
                "2. Run **📋 Sigma Rules** for rule-based detections\n"
                "3. Run **🤖 ML Anomaly** for behavioral anomaly detection\n"
                "4. Run **🎯 Threat Scoring** for unified risk assessment\n"
                "5. Return here to investigate findings"
            )

        lines = ["## 📋 Investigation Summary\n"]
        lines.append(f"**Log Batch:** {len(ctx.raw_hits):,} logs loaded "
                     f"(total matched: {ctx.total_hits:,})")

        if ctx.has_sigma:
            r = ctx.sigma_report
            lines.append(f"**Sigma Detections:** {r.matched_hits} events matched "
                         f"{len(r.triggered_rules)} rules")
            if r.severity_distribution:
                order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
                sev_parts = " | ".join(
                    f"{k.capitalize()}: {v}"
                    for k, v in sorted(r.severity_distribution.items(),
                                       key=lambda x: order.get(x[0].lower(), 9))
                )
                lines.append(f"  Severity breakdown: {sev_parts}")

        if ctx.has_ml:
            s = ctx.ml_summary  # type: ignore[assignment]
            lines.append(f"**ML Anomalies:** {s.get('n_anomalies', 0)} flagged "
                         f"({s.get('anomaly_rate_pct', 0):.1f}% of batch)")

        if ctx.has_threats:
            res = ctx.threat_results
            crit = sum(1 for r in res if r.risk_level == "Critical")
            high = sum(1 for r in res if r.risk_level == "High")
            med  = sum(1 for r in res if r.risk_level == "Medium")
            low  = sum(1 for r in res if r.risk_level == "Low")
            lines.append(
                f"**Threat Alerts:** {len(res)} total — "
                f"🔴 Critical: {crit} | 🟠 High: {high} | "
                f"🟡 Medium: {med} | 🟢 Low: {low}"
            )
            priority = [r for r in res if r.risk_level in ("Critical", "High")][:3]
            if priority:
                lines.append("\n**⚠️ Top Priority Alerts:**")
                for t in priority:
                    lines.append(f"- **{t.risk_level}** (score {t.threat_score}/100) "
                                 f"at {t.timestamp[:19]}: {t.explanation[:100]}…")

        if not (ctx.has_sigma or ctx.has_ml or ctx.has_threats):
            lines.append(
                "\n_No detection engines have been run yet. "
                "Navigate to Sigma Rules, ML Anomaly, and Threat Scoring pages._"
            )

        return "\n".join(lines)

    def _answer_sigma(self) -> str:
        ctx = self.ctx
        if not ctx.has_sigma:
            return (
                "## 📋 Sigma Results Not Available\n\n"
                "Please run the **📋 Sigma Rules** page or the **🎯 Threat Scoring** engine first."
            )

        r = ctx.sigma_report
        lines = ["## 📋 Sigma Rule Detection Analysis\n"]
        lines.append(f"**Events evaluated:** {r.input_hits:,}")
        lines.append(f"**Events matched:** {r.matched_hits:,}")
        lines.append(f"**Rule triggers:** {r.total_rule_triggers:,}")
        lines.append(f"**Elapsed:** {r.elapsed_ms:.0f}ms\n")

        if r.severity_distribution:
            order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "informational": 4}
            icons = {"critical": "🔴", "high": "🟠", "medium": "🟡",
                     "low": "🟢", "informational": "⚪"}
            lines.append("**Severity Breakdown:**")
            for sev, count in sorted(r.severity_distribution.items(),
                                     key=lambda x: order.get(x[0].lower(), 9)):
                icon = icons.get(sev.lower(), "⚫")
                lines.append(f"  {icon} {sev.capitalize()}: {count} events")

        if r.triggered_rules:
            lines.append("\n**Triggered Rules (ranked by hits):**")
            sorted_rules = sorted(
                r.triggered_rules,
                key=lambda x: r.rule_trigger_counts.get(x.rule_id, 0),
                reverse=True
            )
            for rule in sorted_rules[:10]:
                hits = r.rule_trigger_counts.get(rule.rule_id, 0)
                lines.append(f"  • **{rule.title}** [{rule.severity.upper()}] — {hits} hit(s)")
                if rule.description:
                    lines.append(f"    _{rule.description[:100]}_")

        if r.affected_hosts:
            top_h = sorted(r.affected_hosts.items(), key=lambda x: x[1], reverse=True)[:5]
            lines.append(f"\n**Affected Hosts:** {', '.join(f'{h}({n})' for h, n in top_h)}")

        if r.affected_users:
            top_u = sorted(r.affected_users.items(), key=lambda x: x[1], reverse=True)[:5]
            lines.append(f"**Affected Users:** {', '.join(f'{u}({n})' for u, n in top_u)}")

        if r.mitre_tactics:
            lines.append("\n**MITRE ATT&CK Tactics Observed:**")
            for tactic, count in sorted(r.mitre_tactics.items(),
                                        key=lambda x: x[1], reverse=True)[:8]:
                lines.append(f"  • `{tactic}`: {count} matches")

        return "\n".join(lines)

    def _answer_anomaly(self) -> str:
        ctx = self.ctx
        if not ctx.has_ml:
            return (
                "## 🤖 ML Anomaly Results Not Available\n\n"
                "Please run the **🤖 ML Anomaly** page to generate anomaly detection results."
            )

        s = ctx.ml_summary  # type: ignore[assignment]
        lines = ["## 🤖 ML Anomaly Detection Analysis\n"]
        lines.append(f"**Logs analyzed:** {s.get('n_total', 0):,}")
        lines.append(f"**Anomalies detected:** {s.get('n_anomalies', 0):,}")
        lines.append(f"**Anomaly rate:** {s.get('anomaly_rate_pct', 0):.2f}%")
        lines.append(f"**Max score:** {s.get('max_score', 0):.4f}")
        lines.append(f"**Mean score:** {s.get('mean_score', 0):.4f}\n")

        rate = s.get("anomaly_rate_pct", 0)
        if rate > 10:
            lines.append(
                "⚠️ **High anomaly rate.** This may indicate a broad attack, data "
                "quality issues, or unusual batch-wide behavioral patterns."
            )
        elif rate > 3:
            lines.append("🔶 **Moderate anomaly rate.** Investigate the flagged events.")
        else:
            lines.append("✅ **Low anomaly rate.** Batch behavioral patterns appear normal.")

        # Top anomalies
        if ctx.ml_scored_df is not None and "anomaly_score" in ctx.ml_scored_df.columns:
            top = ctx.ml_scored_df.nlargest(5, "anomaly_score")
            lines.append("\n**Top 5 Anomalous Events:**")
            for _, row in top.iterrows():
                doc_id = str(row.get("_id", "?"))[:20]
                score  = row.get("anomaly_score", 0)
                ts     = str(row.get("@timestamp", "?"))[:19]
                lines.append(f"  • `{doc_id}` | Score: {score:.4f} | {ts}")

        lines.append(
            "\n_Anomaly scores reflect deviation from this batch's behavioral baseline. "
            "Higher scores = more unusual behaviour._"
        )
        return "\n".join(lines)

    def _answer_threats(self) -> str:
        ctx = self.ctx
        if not ctx.has_threats:
            return (
                "## 🎯 Threat Scores Not Available\n\n"
                "Please run the **🎯 Threat Scoring** page to generate unified threat scores."
            )

        res = ctx.threat_results
        crit = [r for r in res if r.risk_level == "Critical"]
        high = [r for r in res if r.risk_level == "High"]
        med  = [r for r in res if r.risk_level == "Medium"]
        low  = [r for r in res if r.risk_level == "Low"]

        lines = ["## 🎯 Threat Score Analysis\n"]
        lines.append(f"**Total scored alerts:** {len(res):,}")
        lines.append(
            f"🔴 Critical: {len(crit)} | 🟠 High: {len(high)} | "
            f"🟡 Medium: {len(med)} | 🟢 Low: {len(low)}\n"
        )

        priority = (crit + high)[:5]
        if priority:
            lines.append("**🚨 Priority Alerts (Critical & High):**")
            for t in priority:
                sigma_str = (f" | Rules: {', '.join(t.sigma_matches[:2])}"
                             if t.sigma_matches else "")
                ml_str    = f" | ML: {t.ml_raw:.3f}" if t.ml_raw > 0 else ""
                lines.append(f"\n**[{t.risk_level} — {t.threat_score}/100]** @ {t.timestamp[:19]}")
                lines.append(f"  Doc: `{t.doc_id}`{sigma_str}{ml_str}")
                lines.append(f"  _{t.explanation}_")

        if med:
            lines.append(f"\n**Medium Alerts:** {len(med)} events with moderate risk indicators.")

        # Composition
        sigma_only = sum(1 for r in res if r.sigma_score > 0 and r.ml_score == 0)
        ml_only    = sum(1 for r in res if r.ml_score > 0 and r.sigma_score == 0)
        both       = sum(1 for r in res if r.sigma_score > 0 and r.ml_score > 0)
        lines.append("\n**Score Composition:**")
        lines.append(f"  • Sigma only: {sigma_only}")
        lines.append(f"  • ML only:    {ml_only}")
        lines.append(f"  • Both:       {both}  ← highest confidence")

        return "\n".join(lines)

    def _answer_entities(self, entity_type: str) -> str:
        ctx = self.ctx
        if not ctx.has_data:
            return "No log batch loaded. Please retrieve logs from **📥 Log Retrieval** first."

        counts: Dict[str, int] = {}
        threat_max: Dict[str, int] = {}

        for h in ctx.raw_hits:
            s = h.get("_source", {})
            val = self._extract_entity(s, entity_type)
            if val:
                counts[val] = counts.get(val, 0) + 1

        for t in ctx.threat_results:
            val = self._extract_entity(t.raw_source, entity_type)
            if val:
                threat_max[val] = max(threat_max.get(val, 0), t.threat_score)

        top = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:15]
        labels = {"user": "Users", "host": "Hosts", "ip": "Source IPs"}
        icons  = {"user": "👤", "host": "🖥️", "ip": "🌐"}

        lines = [f"## {icons[entity_type]} Top {labels[entity_type]} in Batch\n"]
        lines.append(f"_(top {len(top)} of {len(counts):,} unique)_\n")
        lines.append(f"| Rank | {labels[entity_type][:-1]} | Events | Max Threat |")
        lines.append("|------|----------|--------|------------|")

        for i, (name, count) in enumerate(top, 1):
            score = threat_max.get(name, 0)
            sicon = ("🔴" if score >= 80 else "🟠" if score >= 60
                     else "🟡" if score >= 40 else "🟢" if score > 0 else "")
            score_str = f"{sicon} {score}" if score > 0 else "—"
            lines.append(f"| {i} | `{name}` | {count:,} | {score_str} |")

        high_risk = [(n, s) for n, s in threat_max.items() if s >= 60]
        if high_risk:
            lines.append(f"\n⚠️ **{len(high_risk)} high-risk {labels[entity_type].lower()}:**")
            for name, score in sorted(high_risk, key=lambda x: x[1], reverse=True)[:3]:
                lines.append(f"  • `{name}` — max threat score: **{score}/100**")

        return "\n".join(lines)

    def _answer_mitre(self) -> str:
        ctx = self.ctx
        if not ctx.has_sigma:
            return (
                "## 🎯 MITRE ATT&CK — No Data\n\n"
                "Sigma detection results are required. "
                "Please run **📋 Sigma Rules** or **🎯 Threat Scoring** first."
            )

        r = ctx.sigma_report
        if not r.mitre_tactics:
            return (
                "No MITRE ATT&CK tactics were mapped in the current Sigma results. "
                "The triggered rules may not carry `attack.*` tags."
            )

        lines = ["## 🎯 MITRE ATT&CK Mapping\n"]
        lines.append("**Observed tactics / techniques (from Sigma rule tags):**\n")

        for tactic, count in sorted(r.mitre_tactics.items(),
                                    key=lambda x: x[1], reverse=True):
            display = tactic.replace("_", " ").title()
            lines.append(f"  • **{display}** — {count} matches")

        lines.append(f"\n**Total unique entries:** {len(r.mitre_tactics)}")

        # Pattern hints
        lateral = [t for t in r.mitre_tactics if "lateral" in t]
        exfil   = [t for t in r.mitre_tactics if "exfil" in t]
        persist = [t for t in r.mitre_tactics if "persistence" in t]
        initial = [t for t in r.mitre_tactics if "initial_access" in t]

        hints = []
        if initial: hints.append("🔓 **Initial Access** — check external-facing services")
        if lateral: hints.append("↔️ **Lateral Movement** — trace internal network pivots")
        if exfil:   hints.append("📤 **Exfiltration** — check outbound data transfers")
        if persist: hints.append("🔁 **Persistence** — check scheduled tasks, startup items")

        if hints:
            lines.append("\n**🔍 Investigation Priorities:**")
            lines.extend(f"  {h}" for h in hints)

        return "\n".join(lines)

    def _answer_explain_event(self, doc_id: Optional[str]) -> str:
        ctx = self.ctx
        threat = None
        if doc_id:
            threat = next((t for t in ctx.threat_results if t.doc_id == doc_id), None)
        if not threat and ctx.has_threats:
            threat = ctx.threat_results[0]   # Default: top threat

        if not threat:
            return (
                "Please specify a Doc ID or run the **🎯 Threat Scoring** engine first.\n"
                "Example: _\"Explain doc ID abc123xyz\"_"
            )

        lines = [f"## 🔍 Event Analysis: `{threat.doc_id}`\n"]
        lines.append(f"**Timestamp:** {threat.timestamp}")
        lines.append(f"**Risk Level:** {threat.risk_level}")
        lines.append(f"**Threat Score:** {threat.threat_score}/100\n")
        lines.append(f"**Explanation:** {threat.explanation}\n")
        lines.append("**Score Breakdown:**")
        lines.append(f"  • Sigma (rule-based): {threat.sigma_score} pts")
        lines.append(f"  • ML (behavioral):    {threat.ml_score} pts "
                     f"(raw isolation score: {threat.ml_raw:.4f})")

        if threat.sigma_matches:
            lines.append(f"\n**Triggered Sigma Rules:**")
            for rule in threat.sigma_matches:
                lines.append(f"  • {rule}")

        if threat.raw_source:
            interesting = [
                ("source.ip",             ("source", "ip")),
                ("destination.ip",        ("destination", "ip")),
                ("user.name",             ("user", "name")),
                ("host.name",             ("host", "name")),
                ("event.category",        ("event", "category")),
                ("event.type",            ("event", "type")),
                ("event.outcome",         ("event", "outcome")),
                ("process.name",          ("process", "name")),
                ("process.command_line",  ("process", "command_line")),
            ]
            lines.append("\n**Key Event Fields:**")
            for label, path in interesting:
                val: Any = threat.raw_source
                for part in path:
                    val = val.get(part) if isinstance(val, dict) else None
                if val:
                    lines.append(f"  • **{label}:** `{val}`")

        return "\n".join(lines)

    def _answer_help(self) -> str:
        lines = ["## 💡 Investigation Assistant Capabilities\n"]
        mode = f"**Mode:** {'🤖 LLM (' + self._provider.value + ')' if self.is_llm_mode else '🔧 Deterministic Fallback'}"
        lines.append(f"{mode} | Operates only on the current session batch\n")

        sections = [
            ("📋 Summary",    ["Summarize the investigation", "What happened?", "Give me an overview"]),
            ("🚨 Sigma Rules", ["Which Sigma rules triggered?", "What are the high severity matches?", "Explain Sigma detections"]),
            ("🤖 ML Anomaly", ["How many anomalies were detected?", "What's the anomaly rate?", "Show top anomalies"]),
            ("🎯 Threats",    ["What are the critical threats?", "Describe the top alerts", "Threat score breakdown"]),
            ("👤 Identity",   ["Who are the top users?", "Show active accounts", "Which users are suspicious?"]),
            ("🖥️ Hosts",      ["Which machines are most active?", "Show affected endpoints"]),
            ("🌐 Network",    ["Show top source IPs", "Network traffic analysis"]),
            ("🎯 MITRE",      ["Map detections to MITRE ATT&CK", "What tactics were observed?"]),
            ("🔍 Event",      ["Explain why this was flagged", "Explain doc ID <id>"]),
        ]

        for title, examples in sections:
            lines.append(f"**{title}:**")
            for ex in examples:
                lines.append(f"  • _{ex}_")
            lines.append("")

        return "\n".join(lines)

    def _answer_general(self, question: str) -> str:
        ctx = self.ctx
        if not ctx.has_data:
            return self._answer_help()

        lines = [f"_I'm not sure how to answer: **\"{question[:80]}\"**_\n"]
        lines.append("**Available data:**")
        lines.append(f"  • Batch: {len(ctx.raw_hits):,} logs")
        if ctx.has_sigma:
            lines.append(f"  • Sigma: {ctx.sigma_report.matched_hits} matches")
        if ctx.has_ml:
            lines.append(f"  • ML: {ctx.ml_summary.get('n_anomalies', 0)} anomalies")  # type: ignore[union-attr]
        if ctx.has_threats:
            crit = sum(1 for r in ctx.threat_results if r.risk_level == "Critical")
            lines.append(f"  • Threats: {len(ctx.threat_results)} alerts ({crit} critical)")

        lines.append("\nTry: _\"Summarize the investigation\"_, _\"What threats are critical?\"_, or _\"Help\"_")
        return "\n".join(lines)

    # ── Utilities ─────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_entity(source: Dict[str, Any], entity_type: str) -> str:
        if entity_type == "user":
            return (source.get("user", {}) or {}).get("name") or source.get("user.name", "")
        if entity_type == "host":
            return (source.get("host", {}) or {}).get("name") or source.get("host.name", "")
        # ip
        return (source.get("source", {}) or {}).get("ip") or source.get("src_ip", "")

    @staticmethod
    def _extract_doc_id(text: str) -> Optional[str]:
        """Try to extract a document ID from free text."""
        quoted = re.findall(r'["\']([^"\']+)["\']', text)
        if quoted:
            return quoted[0]
        hex_like = re.findall(r'\b([A-Za-z0-9_-]{15,})\b', text)
        if hex_like:
            return hex_like[0]
        return None

    # ── Report generation ─────────────────────────────────────────────────────

    def get_context_summary(self) -> str:
        """Return the compact context text (for display in the UI)."""
        return self._context_text

    def generate_report(self, chat_history: List[Dict[str, str]]) -> str:
        """Generate a downloadable markdown investigation report."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        lines = [
            "# SOC Investigation Report",
            f"_Generated by ISRO SOC Analytics · AI Assistant · {now}_\n",
            "## Session Context\n",
            "```",
            self._context_text,
            "```\n",
            "## Investigation Q&A\n",
        ]

        for msg in chat_history:
            role    = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                lines.append(f"**🔍 Analyst:** {content}\n")
            elif role == "assistant":
                lines.append(f"**🤖 Assistant:**\n{content}\n")
            lines.append("---\n")

        return "\n".join(lines)
