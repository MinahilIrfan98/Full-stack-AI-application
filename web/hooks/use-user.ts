"use client";

import { useEffect, useState } from "react";
import { fetchUserProfile, type UserProfile } from "@/lib/api";

export function useUser() {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    async function loadUser() {
      try {
        const profile = await fetchUserProfile();
        setUser(profile);
      } catch (err) {
        setError(err instanceof Error ? err : new Error("Failed to load user profile"));
      } finally {
        setLoading(false);
      }
    }
    loadUser();
  }, []);

  return { user, loading, error };
}
