import { OrganizationDetailPage } from "@/features/workspace-config";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <OrganizationDetailPage organizationId={id} />;
}
