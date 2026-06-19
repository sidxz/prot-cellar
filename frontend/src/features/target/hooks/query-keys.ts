export const TARGETS_KEY = ["targets"] as const;

export const targetDetailKey = (id: string) => [...TARGETS_KEY, id] as const;
