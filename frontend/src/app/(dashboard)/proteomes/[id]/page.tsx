import { ProteomeDetailPage } from "@/features/taxonomy";

export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ProteomeDetailPage proteomeId={decodeURIComponent(id)} />;
}
