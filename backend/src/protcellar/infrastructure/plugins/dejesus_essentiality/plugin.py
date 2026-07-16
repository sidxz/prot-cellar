from __future__ import annotations

import uuid

from protcellar.application.plugins.context import PluginRunContext
from protcellar.application.plugins.manifest import PluginManifest
from protcellar.application.target_biology.bulk_upsert_essentiality import EssentialityImportRecord
from protcellar.infrastructure.ingestion.dejesus_essentiality import parse_dejesus_essentiality
from protcellar.infrastructure.plugins.dejesus_essentiality.manifest import MANIFEST

_DEJESUS_PMID = "28096490"
_DEJESUS_DATASET = "DeJesus 2017"


class DejesusEssentialityPlugin:
    @staticmethod
    def manifest() -> PluginManifest:
        return MANIFEST

    async def run(self, ctx: PluginRunContext) -> None:
        # The upload endpoint already normalized XLSX/CSV -> TSV; load_upload
        # returns that TSV text. utf-8-sig tolerates a BOM from Excel exports.
        upload_ref = uuid.UUID(str(ctx.params["upload_ref"]))
        text = (await ctx.load_upload(upload_ref)).decode("utf-8-sig")
        calls = parse_dejesus_essentiality(text)  # {locus_tag: normalized_call}
        condition = ctx.params.get("condition") or None

        records = [
            EssentialityImportRecord(
                locus_key=locus,
                classification=call,
                condition=condition,
                method="TnSeq",
                pmid=_DEJESUS_PMID,
                dataset=_DEJESUS_DATASET,
            )
            for locus, call in calls.items()
        ]
        await ctx.reporter.advance(0, len(records))
        await ctx.sink.upsert("essentiality", records)
        await ctx.reporter.advance(len(records), len(records))


plugin = DejesusEssentialityPlugin()
