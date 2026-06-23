import { memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type MarkdownViewProps = {
  content: string;
  className?: string;
};

/** Render Markdown (with GFM: tables, task lists, autolinks) into rich text. */
export const MarkdownView = memo(function MarkdownView({ content, className }: MarkdownViewProps) {
  return (
    <div className={`markdown-body${className ? ` ${className}` : ""}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
});
