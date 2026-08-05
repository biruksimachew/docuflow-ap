"use client";

import {
  useEffect,
} from "react";


type WorkspaceErrorProps = {
  error: Error & {
    digest?: string;
  };
  reset: () => void;
};


export default function WorkspaceError({
  error,
  reset,
}: WorkspaceErrorProps) {
  useEffect(() => {
    console.error(
      "DocuFlow workspace error",
      error,
    );
  }, [error]);

  return (
    <section className="panel workspace-error">
      <div className="empty-icon">
        !
      </div>
      <h2>
        The operations workspace could not load
      </h2>
      <p>
        Retry once. If the problem continues,
        inspect the API and frontend logs.
      </p>
      <button
        type="button"
        className="primary-action"
        onClick={reset}
      >
        Retry
      </button>
    </section>
  );
}
