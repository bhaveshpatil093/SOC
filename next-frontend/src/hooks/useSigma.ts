import { useQuery } from "@tanstack/react-query";
import { 
  fetchSigmaOverview,
  fetchSigmaRules,
  fetchSigmaCoverage
} from "../lib/api/client";
import { 
  SigmaOverview, 
  SigmaRuleStat, 
  SigmaCoverage 
} from "../types/sigma";

export function useSigmaOverview() {
  return useQuery<SigmaOverview>({
    queryKey: ["sigma", "overview"],
    queryFn: fetchSigmaOverview,
    refetchInterval: 60000,
  });
}

export function useSigmaRules() {
  return useQuery<SigmaRuleStat[]>({
    queryKey: ["sigma", "rules"],
    queryFn: fetchSigmaRules,
    refetchInterval: 60000,
  });
}

export function useSigmaCoverage() {
  return useQuery<SigmaCoverage[]>({
    queryKey: ["sigma", "coverage"],
    queryFn: fetchSigmaCoverage,
    refetchInterval: 60000,
  });
}
