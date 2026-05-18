"use client";

import { Component, ReactNode } from "react";
import { Button } from "@/components/Button";

type Props = {
  children: ReactNode;
  fallback?: ReactNode;
};

type State = {
  hasError: boolean;
  message: string;
};

/**
 * React error boundary that catches rendering errors and shows a recovery UI.
 * Wrap page sections that depend on external data with this component.
 *
 * Usage:
 *   <ErrorBoundary>
 *     <MyDataComponent />
 *   </ErrorBoundary>
 */
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, message: "" };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message };
  }

  componentDidCatch(error: Error, info: { componentStack: string }) {
    // In production you would send this to an error monitoring service
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  reset = () => this.setState({ hasError: false, message: "" });

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div className="rounded border border-rose-200 bg-rose-50 p-6 text-center">
          <p className="font-semibold text-rose-700">Something went wrong</p>
          {this.state.message && (
            <p className="mt-1 text-sm text-rose-600">{this.state.message}</p>
          )}
          <Button variant="secondary" className="mt-4" onClick={this.reset}>
            Try again
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}
