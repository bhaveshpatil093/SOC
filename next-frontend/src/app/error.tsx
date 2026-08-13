"use client";

import { useEffect } from "react";

export default function Error({ error, reset }: { error: Error & { digest?: string }, reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="p-8">
      <h2>Something went wrong!</h2>
      <button onClick={() => reset()} className="mt-4 px-4 py-2 bg-primary text-white rounded">
        Try again
      </button>
    </div>
  );
}