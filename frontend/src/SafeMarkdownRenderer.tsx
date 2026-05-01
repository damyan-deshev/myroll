import ReactMarkdown from "react-markdown";

export function SafeMarkdownRenderer({ body }: { body: string }) {
  return (
    <div className="safe-markdown">
      <ReactMarkdown
        components={{
          a: ({ children }) => <span>{children}</span>
        }}
      >
        {body}
      </ReactMarkdown>
    </div>
  );
}
