import {
  softFailureMessage,
  type ChatSource,
  type RetrievalDebugMetadata,
} from "../../lib/api";
import { formatResponseMetadata } from "../../lib/citations";
import RetrievalInspector from "../RetrievalInspector";
import { InlineAlert } from "../ui/InlineAlert";

export type AiResponseContentProps = {
  text?: string;
  error?: { code: string; message: string };
  sources?: ChatSource[];
  chunks?: number;
  model?: string;
  latencyMs?: number;
  question?: string;
  retrievalDebug?: RetrievalDebugMetadata;
  /** When false, hide error, zero-chunks, metadata, and inspector. */
  detailsVisible?: boolean;
  /** Show a blinking cursor after text while tokens are in flight. */
  isStreaming?: boolean;
  /** Shown when there is no text and streaming is not active. */
  emptyMessage?: string;
  /** Shown when chunks === 0 and showZeroChunks is true. */
  zeroChunksMessage?: string;
  showZeroChunks?: boolean;
  textClassName?: string;
  metadataClassName?: string;
  zeroChunksClassName?: string;
  emptyMessageClassName?: string;
};

export default function AiResponseContent({
  text,
  error,
  sources,
  chunks,
  model,
  latencyMs,
  question,
  retrievalDebug,
  detailsVisible = true,
  isStreaming = false,
  emptyMessage,
  zeroChunksMessage = "No relevant content found in this document.",
  showZeroChunks = true,
  textClassName = "",
  metadataClassName = "mt-2 text-xs text-muted",
  zeroChunksClassName = "mt-1 text-sm text-muted italic",
  emptyMessageClassName = "text-sm text-muted italic",
}: AiResponseContentProps) {
  const metadata = formatResponseMetadata({
    chunks,
    model,
    latency_ms: latencyMs,
  });

  return (
    <>
      {error && detailsVisible && (
        <div className="mb-2">
          <InlineAlert>{softFailureMessage(error)}</InlineAlert>
        </div>
      )}
      {isStreaming ? (
        text ? (
          textClassName ? (
            <p className={textClassName}>
              {text}
              <span className="inline-block w-[2px] h-[1em] bg-accent animate-pulse ml-0.5 align-text-bottom" />
            </p>
          ) : (
            <span>
              {text}
              <span className="inline-block w-[2px] h-[1em] bg-accent animate-pulse ml-0.5 align-text-bottom" />
            </span>
          )
        ) : (
          <span className="text-muted animate-pulse">Streaming...</span>
        )
      ) : text ? (
        textClassName ? (
          <p className={textClassName}>{text}</p>
        ) : (
          text
        )
      ) : emptyMessage ? (
        <p className={emptyMessageClassName}>{emptyMessage}</p>
      ) : null}
      {showZeroChunks && chunks === 0 && detailsVisible && (
        <p className={zeroChunksClassName}>{zeroChunksMessage}</p>
      )}
      {metadata && detailsVisible && (
        <p className={metadataClassName}>{metadata}</p>
      )}
      {detailsVisible && (
        <RetrievalInspector
          data={{
            question,
            retrieval_debug: retrievalDebug,
            sources,
            chunks,
            model,
            latency_ms: latencyMs,
          }}
        />
      )}
    </>
  );
}
