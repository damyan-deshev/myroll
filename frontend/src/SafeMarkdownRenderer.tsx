import type { ReactNode } from "react";
import ReactMarkdown from "react-markdown";

export function SafeMarkdownRenderer({ body }: { body: string }) {
  const Heading = ({ children }: { children?: ReactNode }) => (
    <p>
      <strong>{children}</strong>
    </p>
  );
  return (
    <div className="safe-markdown">
      <ReactMarkdown
        components={{
          a: ({ children }) => <span>{children}</span>,
          img: ({ alt }) => <span>{alt ?? ""}</span>,
          h1: Heading,
          h2: Heading,
          h3: Heading,
          h4: Heading,
          h5: Heading,
          h6: Heading,
          code: ({ children }) => <span>{children}</span>,
          pre: ({ children }) => <div>{children}</div>
        }}
      >
        {body}
      </ReactMarkdown>
    </div>
  );
}
