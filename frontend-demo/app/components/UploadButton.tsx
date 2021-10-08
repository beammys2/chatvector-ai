"use client";

import { Paperclip } from "lucide-react";
import { forwardRef } from "react";

type Props = {
  onClick: () => void;
  disabled?: boolean;
};

const UploadButton = forwardRef<HTMLButtonElement, Props>(function UploadButton(
  { onClick, disabled = false },
  ref,
) {
  return (
    <button
      ref={ref}
      type="button"
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      className={`transition ${disabled ? "cursor-not-allowed text-muted/30" : "text-muted hover:text-foreground"}`}
      title={disabled ? "Remove the current document before uploading a new one" : "Upload document"}
      aria-label="Upload document"
    >
      <Paperclip size={18} />
    </button>
  );
});

export default UploadButton;