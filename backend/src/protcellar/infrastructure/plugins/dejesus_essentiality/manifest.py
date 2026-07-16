from __future__ import annotations

from protcellar.application.plugins.manifest import ParamField, ParamType, PluginManifest
from protcellar.domain.shared.provenance import GenerationMethod

MANIFEST = PluginManifest(
    id="dejesus_essentiality",
    version="1.0.0",
    name="DeJesus essentiality",
    description="Load gene essentiality calls from a published DeJesus 2017 TnSeq table.",
    target_records=("essentiality",),
    default_generation_method=GenerationMethod.IMPORTED,
    params=(
        ParamField(
            key="organism_id",
            label="Organism",
            type=ParamType.ORGANISM,
            required=True,
            help="Strain the loci belong to (default M. tuberculosis H37Rv, tax 83332).",
        ),
        ParamField(
            key="upload",
            label="DeJesus table",
            type=ParamType.FILE_UPLOAD,
            required=True,
            help="Published essentiality table (XLSX/CSV/TSV; normalized to TSV on upload).",
        ),
        ParamField(
            key="condition",
            label="Condition",
            type=ParamType.STRING,
            required=False,
            help="Optional growth condition tagged on every row (e.g. 'in vitro 7H9').",
        ),
    ),
    requires_secrets=(),
)
