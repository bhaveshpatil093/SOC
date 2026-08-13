"use client";

import React, { Component, ReactNode } from "react";
import { AlertCircle, RefreshCw } from "lucide-react";

interface Props {
  children: ReactNode;
  fallbackMessage?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class WidgetErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("Widget Error:", error, errorInfo);
  }

  private handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-full min-h-[250px] p-6 bg-red-950/10 border border-red-900/30 rounded-xl">
          <AlertCircle className="w-10 h-10 text-red-500 mb-4 opacity-80" />
          <h3 className="text-white font-medium mb-2">Component Failure</h3>
          <p className="text-sm text-red-300/70 text-center max-w-sm mb-6">
            {this.props.fallbackMessage || this.state.error?.message || "An unexpected error occurred while rendering this component."}
          </p>
          <button 
            onClick={this.handleRetry}
            className="flex items-center gap-2 px-4 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20 rounded-md transition-colors text-sm"
          >
            <RefreshCw className="w-4 h-4" />
            Retry Component
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
