import { ClipboardCheck } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

/**
 * Hasibu, with the one-line description of what it is.
 *
 * persona.md names Hasibu as a public-sector evidence officer, so the same name and the same
 * description are used here rather than a second name for the interface. The tagline is the sentence
 * the project leads with: this produces evidence for a committee, and it does not decide.
 */
export function Header() {
  const { pathname } = useLocation();
  return (
    <header className="no-print border-b border-blue-100 bg-paper/95 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-5 py-3">
        <Link to="/" className="flex min-w-0 items-center gap-3">
          <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-accent text-paper shadow-soft">
            <ClipboardCheck className="size-4" aria-hidden="true" />
          </span>
          <span className="min-w-0">
            <span className="block text-base font-semibold tracking-tight text-ink-900">Hasibu</span>
            <span className="hidden text-[0.7rem] text-ink-500 sm:block">Evidence for a tender committee</span>
          </span>
        </Link>
        <nav className="flex items-center gap-1 text-sm" aria-label="Primary navigation">
          <Link
            to="/"
            className={
              pathname === "/" ? "rounded px-2 py-1 font-medium text-ink-900" : "rounded px-2 py-1 text-ink-500 hover:text-ink-900"
            }
          >
            Start
          </Link>
          <Link
            to="/runs"
            className={
              pathname.startsWith("/runs")
                ? "rounded px-2 py-1 font-medium text-ink-900"
                : "rounded px-2 py-1 text-ink-500 hover:text-ink-900"
            }
          >
            All runs
          </Link>
        </nav>
      </div>
    </header>
  );
}
