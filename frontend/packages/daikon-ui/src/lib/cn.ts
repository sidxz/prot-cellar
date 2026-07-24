import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** Suite-standard class merge (clsx + tailwind-merge), copied so the package
 *  owns no import into a host app. Identical to each app's shared/lib cn. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
