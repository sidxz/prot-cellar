import { OrganismDetailPage } from "@/features/taxonomy";

export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <OrganismDetailPage organismId={decodeURIComponent(id)} />;
}
