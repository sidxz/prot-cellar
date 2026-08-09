import { ExtensionFieldEditor } from "@/features/extension-fields";

export default async function Page({ params }: { params: Promise<{ kind: string }> }) {
  const { kind } = await params;
  return <ExtensionFieldEditor key={kind} kind={kind} />;
}
