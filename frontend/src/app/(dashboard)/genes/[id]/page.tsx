import { GeneDetailPage } from "@/features/protein-catalog";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <GeneDetailPage geneId={id} />;
}
