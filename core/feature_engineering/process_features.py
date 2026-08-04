"""
core/feature_engineering/process_features.py

Extracts Process Behaviour metrics:
- Rare process execution
- Suspicious command line
- PowerShell/Bash frequency
- Parent-child process rarity

Why it is useful:
Detects Living off the Land (LOLBins) and suspicious obfuscation (e.g. Base64 strings in cmd).

Mathematical formula:
- Rarity = 1 / Count(process)
- Suspicious Cmdline = Binary flag 1 if regex match, else 0.
"""

import pandas as pd
import re
from .base import BaseFeatureExtractor, FeatureContext

class ProcessFeatureExtractor(BaseFeatureExtractor):
    
    PROCESS_ALIASES = ["process.name", "process_name", "Image"]
    CMD_ALIASES = ["process.command_line", "process_command_line", "CommandLine"]
    PARENT_ALIASES = ["process.parent.name", "process_parent_name", "ParentImage"]
    
    # Common LOLBins and script engines
    SCRIPT_ENGINES = ["powershell.exe", "pwsh.exe", "cmd.exe", "bash", "sh", "zsh", "wscript.exe", "cscript.exe"]
    
    # Regex for suspicious patterns: Base64 padding, bypass flags, download cradles
    SUSPICIOUS_PATTERN = re.compile(
        r'([A-Za-z0-9+/]{20,}={0,2}|-enc|-ExecutionPolicy\s+Bypass|-nop|-hidden|iex|Invoke-WebRequest|wget|curl)', 
        re.IGNORECASE
    )
    
    def fit_transform(self, df: pd.DataFrame, context: FeatureContext) -> pd.DataFrame:
        result = df.copy()
        
        process_col = self._resolve_col(df, self.PROCESS_ALIASES)
        cmd_col = self._resolve_col(df, self.CMD_ALIASES)
        parent_col = self._resolve_col(df, self.PARENT_ALIASES)
        
        if process_col:
            # 1. Rare process execution
            proc_counts = df[process_col].value_counts(normalize=True)
            result[f"{self.FEAT_PREFIX}process_rarity"] = 1.0 - result[process_col].map(proc_counts).fillna(0)
            
            # 2. PowerShell/Bash frequency
            is_script_engine = df[process_col].astype(str).str.lower().isin(self.SCRIPT_ENGINES)
            result[f"{self.FEAT_PREFIX}process_is_script_engine"] = is_script_engine.astype(float)
            
            # 3. Parent-child process rarity
            if parent_col:
                # Combine parent and child to form a relationship string
                parent_child = df[parent_col].astype(str) + " -> " + df[process_col].astype(str)
                pc_counts = parent_child.value_counts(normalize=True)
                result[f"{self.FEAT_PREFIX}process_parent_child_rarity"] = 1.0 - parent_child.map(pc_counts).fillna(0)
        
        if cmd_col:
            # 4. Suspicious command line
            def check_suspicious(cmd):
                if not isinstance(cmd, str): return 0.0
                return 1.0 if self.SUSPICIOUS_PATTERN.search(cmd) else 0.0
                
            result[f"{self.FEAT_PREFIX}process_suspicious_cmd"] = result[cmd_col].apply(check_suspicious)
            
        return result
