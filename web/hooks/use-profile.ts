"use client";

import { useCallback, useEffect, useState } from "react";

const PROFILE_NAME_KEY = "openchat_profile_name";

export function useProfile() {
  const [name, setName] = useState("");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const storedName = window.localStorage.getItem(PROFILE_NAME_KEY)?.trim() ?? "";
    setName(storedName.slice(0, 40));
    setReady(true);
  }, []);

  const saveName = useCallback((value: string) => {
    const trimmed = value.trim().slice(0, 40);
    if (!trimmed) return false;
    window.localStorage.setItem(PROFILE_NAME_KEY, trimmed);
    setName(trimmed);
    return true;
  }, []);

  return { name, ready, saveName };
}
