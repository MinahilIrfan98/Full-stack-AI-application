"use client";

import { useEffect, useRef, useState } from "react";
import { MicIcon, PhoneOffIcon } from "lucide-react";
import { Room, RoomEvent, Track, type Participant } from "livekit-client";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { ApiError, createVoiceToken } from "@/lib/api";

export function VoiceCall({
  onTranscript,
}: {
  onTranscript: (role: "user" | "assistant", text: string) => void;
}) {
  const [connecting, setConnecting] = useState(false);
  const [connected, setConnected] = useState(false);
  const roomRef = useRef<Room | null>(null);
  const audioElements = useRef<Set<HTMLElement>>(new Set());
  const seenSegments = useRef<Set<string>>(new Set());

  const endCall = async () => {
    const room = roomRef.current;
    roomRef.current = null;
    if (room) await room.disconnect();
    audioElements.current.forEach((element) => {
      element.remove();
    });
    audioElements.current.clear();
    setConnected(false);
    setConnecting(false);
  };

  const startCall = async () => {
    setConnecting(true);
    seenSegments.current.clear();
    let room: Room | null = null;
    try {
      const credentials = await createVoiceToken();
      room = new Room({ adaptiveStream: true, dynacast: true });
      roomRef.current = room;
      room.on(RoomEvent.TrackSubscribed, (track) => {
        if (track.kind !== Track.Kind.Audio) return;
        const element = track.attach();
        audioElements.current.add(element);
        document.body.appendChild(element);
      });
      room.on(RoomEvent.TrackUnsubscribed, (track) => {
        track.detach().forEach((element) => {
          audioElements.current.delete(element);
          element.remove();
        });
      });
      room.on(
        RoomEvent.TranscriptionReceived,
        (segments, participant?: Participant) => {
          const role = participant?.identity === room?.localParticipant.identity ? "user" : "assistant";
          for (const segment of segments) {
            if (!segment.final || seenSegments.current.has(segment.id)) continue;
            seenSegments.current.add(segment.id);
            onTranscript(role, segment.text);
          }
        },
      );
      room.on(RoomEvent.Disconnected, () => {
        if (roomRef.current === room) {
          roomRef.current = null;
          setConnected(false);
          setConnecting(false);
        }
      });
      await room.connect(credentials.server_url, credentials.participant_token);
      await room.localParticipant.setMicrophoneEnabled(true);
      setConnected(true);
    } catch (error) {
      if (room) await room.disconnect();
      if (roomRef.current === room) roomRef.current = null;
      const message = error instanceof ApiError ? error.message : (error as Error).message;
      toast.error(message || "Couldn't start the voice call.");
      setConnecting(false);
      setConnected(false);
    }
  };

  useEffect(() => () => {
    const room = roomRef.current;
    roomRef.current = null;
    if (room) void room.disconnect();
    audioElements.current.forEach((element) => element.remove());
    audioElements.current.clear();
  }, []);

  const label = connected ? "End voice chat" : connecting ? "Connecting…" : "Start voice chat";

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          type="button"
          variant={connected ? "destructive" : "ghost"}
          size="icon-sm"
          disabled={connecting}
          aria-label={label}
          onClick={() => (connected ? void endCall() : void startCall())}
        >
          {connected ? <PhoneOffIcon /> : <MicIcon />}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}
