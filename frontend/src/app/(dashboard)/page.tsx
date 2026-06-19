import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/shared/components/ui/card";
import { Boxes, Dna, FlaskConical } from "lucide-react";
import Link from "next/link";

const quickLinks = [
  {
    title: "Proteins",
    description: "Browse and manage protein entries",
    href: "/proteins",
    icon: Dna,
  },
  {
    title: "Targets",
    description: "Drug targets and binding sites",
    href: "/targets",
    icon: FlaskConical,
  },
  {
    title: "Organisms",
    description: "Taxonomy and organism catalog",
    href: "/organisms",
    icon: Boxes,
  },
];

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">prot-cellar</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Protein &amp; target management platform
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {quickLinks.map(({ title, description, href, icon: Icon }) => (
          <Link key={href} href={href} className="block">
            <Card className="h-full transition-colors hover:bg-accent/50">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Icon className="h-5 w-5 text-primary" />
                  <CardTitle>{title}</CardTitle>
                </div>
                <CardDescription>{description}</CardDescription>
              </CardHeader>
              <CardContent>
                <span className="text-xs text-muted-foreground">Open →</span>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
