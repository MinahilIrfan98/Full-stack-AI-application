"use client";

import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { ArrowUpIcon, ImageIcon, SquareIcon, FileIcon, X, LoaderCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { VoiceCall } from "@/components/chat/voice-call";
import { APP_CONFIG } from "@/lib/config";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { deleteUploadedFile, uploadFile } from "@/lib/api";
import type { MessageAttachment } from "@/lib/types";

export function Composer({
  onSend,
  onStop,
  onVoiceTranscript,
  streaming,
  disabled,
  placeholder = `Message ${APP_CONFIG.appName}…`,
  autoFocus,
}: {
  onSend: (
    text: string,
    images?: string[],
    fileContext?: { filename: string; file_id: string },
    attachments?: MessageAttachment[],
  ) => void;
  onStop: () => void;
  onVoiceTranscript: (role: "user" | "assistant", text: string) => void;
  streaming: boolean;
  disabled?: boolean;
  placeholder?: string;
  autoFocus?: boolean;
}) {
  const [value, setValue] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const [imageAttachment, setImageAttachment] = useState<MessageAttachment | null>(null);
  const [attachedFile, setAttachedFile] = useState<
    ({ filename: string; file_id: string } & MessageAttachment) | null
  >(null);
  const [uploading, setUploading] = useState(false);
  const ref = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const docRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (autoFocus && window.matchMedia("(min-width: 768px)").matches) ref.current?.focus();
  }, [autoFocus]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onloadend = () => {
      const previewUrl = reader.result as string;
      setPreview(previewUrl);
      setImageAttachment({
        filename: file.name,
        size: file.size,
        mimeType: file.type,
        previewUrl,
      });
    };
    reader.readAsDataURL(file);
    e.target.value = "";
  };

  const handleDocChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    try {
      const res = await uploadFile(file);
      setAttachedFile({
        filename: res.filename,
        file_id: res.file_id,
        size: file.size,
        mimeType: file.type,
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to upload file";
      toast.error(msg);
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    if (streaming) return onStop();
    if (!value.trim() && !preview && !attachedFile) return;
    if (disabled || uploading) return;
    const attachments: MessageAttachment[] = [];
    if (imageAttachment) attachments.push(imageAttachment);
    if (attachedFile) attachments.push(attachedFile);
    onSend(
      value,
      preview ? [preview.split(",")[1]] : undefined,
      attachedFile
        ? {
            filename: attachedFile.filename,
            file_id: attachedFile.file_id,
          }
        : undefined,
      attachments.length ? attachments : undefined,
    );
    setValue("");
    setPreview(null);
    setImageAttachment(null);
    setAttachedFile(null);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    const touch = window.matchMedia("(hover: none)").matches;
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing && !touch) {
      e.preventDefault();
      submit();
    }
  };

  const canSend =
    streaming || ((!!value.trim() || !!preview || !!attachedFile) && !disabled && !uploading);

  return (
    <form
      onSubmit={submit}
      className="mx-auto w-full max-w-3xl rounded-3xl border bg-card p-2.5 pl-4 shadow-sm transition-colors focus-within:border-ring"
    >
      {(preview || attachedFile) && (
        <div className="flex flex-wrap gap-2 mb-2 px-2">
          {preview && (
            <div className="relative h-20 w-20 overflow-hidden rounded-lg border bg-muted">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={preview} alt="Preview" className="h-full w-full object-cover" />
              <button
                type="button"
                onClick={() => {
                  setPreview(null);
                  setImageAttachment(null);
                }}
                className="absolute right-0 top-0 flex size-4 items-center justify-center rounded-full bg-destructive text-[10px] font-bold text-destructive-foreground"
              >
                ×
              </button>
            </div>
          )}
          {attachedFile && (
            <div className="flex items-center gap-2 rounded-lg border bg-muted px-2 py-1 text-xs font-medium text-muted-foreground">
              <FileIcon className="size-3" />
              <span className="max-w-[150px] truncate">{attachedFile.filename}</span>
              <button
                type="button"
                onClick={async () => {
                  try {
                    await deleteUploadedFile(attachedFile.file_id);
                    setAttachedFile(null);
                  } catch (err) {
                    toast.error(err instanceof Error ? err.message : "Could not remove file");
                  }
                }}
                aria-label={`Remove ${attachedFile.filename}`}
                className="ml-1 flex size-3 items-center justify-center rounded-full hover:bg-muted-foreground/20"
              >
                <X className="size-3" />
              </button>
            </div>
          )}
        </div>
      )}
      <label htmlFor="composer" className="sr-only">
        Message
      </label>
      <div className="flex min-w-0 items-end gap-2">
        <textarea
          id="composer"
          ref={ref}
          rows={1}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={placeholder}
          enterKeyHint="send"
          className="field-sizing-content max-h-52 min-h-7 min-w-0 flex-1 resize-none bg-transparent py-1.5 text-[15px] leading-6 outline-none placeholder:text-muted-foreground"
        />
        <div className="flex shrink-0 items-center gap-1">
          <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={handleFileChange} />
          <input
            ref={docRef}
            type="file"
            accept=".txt,.md,.csv,.json,.pdf,.docx,.py,.js,.jsx,.ts,.tsx,.html,.css,.sql,.sh,.yaml,.yml,.toml,.xml,.java,.c,.h,.cpp,.go,.rs,.ipynb"
            className="hidden"
            onChange={handleDocChange}
          />
          <VoiceCall onTranscript={onVoiceTranscript} />
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label="Upload image"
                onClick={() => fileRef.current?.click()}
              >
                <ImageIcon className="text-muted-foreground" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Upload image</TooltipContent>
          </Tooltip>
          {uploading && (
            <div className="flex items-center gap-1 text-xs text-muted-foreground" role="status">
              <LoaderCircle className="size-3 animate-spin" />
              <span>Processing file…</span>
            </div>
          )}
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label="Upload document"
                onClick={() => docRef.current?.click()}
                disabled={uploading}
              >
                <FileIcon className="text-muted-foreground" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Upload document</TooltipContent>
          </Tooltip>
          <Button
            type="submit"
            size="icon"
            disabled={!canSend}
            aria-label={streaming ? "Stop generating" : "Send message"}
            className={cn("rounded-full", !canSend && "opacity-30")}
          >
            {streaming ? <SquareIcon className="size-3.5 fill-current" /> : <ArrowUpIcon />}
          </Button>
        </div>
      </div>
    </form>  );
}
