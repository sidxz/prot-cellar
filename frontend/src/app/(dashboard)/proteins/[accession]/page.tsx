import { ProteinDetailPage } from "@/features/protein-catalog";

export default async function Page({
  params,
}: {
  params: Promise<{ accession: string }>;
}) {
  const { accession } = await params;
  return <ProteinDetailPage accession={decodeURIComponent(accession)} />;
}
