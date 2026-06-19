import type { LucideIcon } from "lucide-react";
import {
  Boxes,
  Building2,
  Dna,
  FlaskConical,
  Layers,
  LayoutDashboard,
  Microscope,
  Network,
  ScrollText,
} from "lucide-react";

export interface NavItem {
  title: string;
  href: string;
  icon: LucideIcon;
  children?: NavItem[];
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const navigation: { home: NavItem; groups: NavGroup[] } = {
  home: { title: "Dashboard", href: "/", icon: LayoutDashboard },
  groups: [
    {
      label: "Catalog",
      items: [
        { title: "Proteins", href: "/proteins", icon: Dna },
        { title: "Genes", href: "/genes", icon: Network },
        { title: "Targets", href: "/targets", icon: FlaskConical },
      ],
    },
    {
      label: "Taxonomy",
      items: [
        { title: "Organisms", href: "/organisms", icon: Microscope },
        { title: "Strains", href: "/strains", icon: Boxes },
        { title: "Proteomes", href: "/proteomes", icon: Layers },
      ],
    },
    {
      label: "Administration",
      items: [
        { title: "Organizations", href: "/admin/organizations", icon: Building2 },
        { title: "Audit", href: "/admin/audit", icon: ScrollText },
      ],
    },
  ],
};
