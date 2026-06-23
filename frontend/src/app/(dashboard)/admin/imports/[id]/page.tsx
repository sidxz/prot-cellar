import { ImportDetailPage } from "@/features/import-hub";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ImportDetailPage importRunId={id} />;
}
