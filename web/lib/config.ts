/**
 * App-wide display settings. Change these to rebrand the app for a client.
 */
export const APP_CONFIG = {
  appName: "Assistant",
  appDescription: "AI assistant powered by local and cloud models",
} as const;

export const firstNameOf = (name: string) => name.trim().split(/\s+/)[0] ?? name;
