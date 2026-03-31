import { Component } from 'react';

/**
 * React error boundary that catches unhandled render/lifecycle errors and
 * shows a fallback UI instead of crashing the entire app.
 *
 * Usage:
 *   <ErrorBoundary>
 *     <SomePage />
 *   </ErrorBoundary>
 */
export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error('[ErrorBoundary] Unhandled render error:', error, info);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center min-h-screen gap-4 p-8 text-center">
          <h2 className="text-2xl font-semibold text-destructive">Something went wrong</h2>
          <p className="text-muted-foreground max-w-md">
            An unexpected error occurred. You can try reloading the page or navigating back.
          </p>
          {this.state.error && (
            <pre className="text-xs text-left bg-muted rounded p-4 max-w-xl overflow-auto">
              {String(this.state.error)}
            </pre>
          )}
          <div className="flex gap-2">
            <button
              className="px-4 py-2 rounded bg-primary text-primary-foreground hover:opacity-90"
              onClick={this.handleReset}
            >
              Try again
            </button>
            <button
              className="px-4 py-2 rounded border hover:bg-muted"
              onClick={() => window.location.reload()}
            >
              Reload page
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
