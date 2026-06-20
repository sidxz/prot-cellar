import { describe, expect, it } from "vitest";

import type { Protein } from "../types";
import {
  commentsByType,
  featuresByCategory,
  goTermsByAspect,
  structures,
} from "./protein-annotations";

const fixture = {
  comments: [
    { comment_type: "FUNCTION", text: "Catalyzes X." },
    { comment_type: "COFACTOR", text: "Binds Mg2+." },
    { comment_type: "FUNCTION", text: "Also does Y." },
  ],
  cross_references: [
    {
      database: "GO",
      accession: "GO:0016491",
      url: "http://go/1",
      properties: { GoTerm: "F:oxidoreductase activity", GoEvidence: "IEA:UniProt" },
    },
    {
      database: "GO",
      accession: "GO:0006281",
      url: "http://go/2",
      properties: { GoTerm: "P:DNA repair" },
    },
    {
      database: "GO",
      accession: "GO:0005737",
      url: "http://go/3",
      properties: { GoTerm: "C:cytoplasm" },
    },
    {
      database: "PDB",
      accession: "1ABC",
      url: "http://pdb/1",
      properties: { Method: "X-ray", Resolution: "2.10 A", Chains: "A=1-300" },
    },
    { database: "AlphaFoldDB", accession: "P12345", url: "http://af/1", properties: {} },
    { database: "InterPro", accession: "IPR000001", url: "http://ip/1", properties: {} },
  ],
  features: [
    { feature_type: "ACT_SITE", start: 100, end: 100, description: "Proton acceptor" },
    { feature_type: "HELIX", start: 10, end: 20 },
  ],
} as unknown as Protein;

describe("protein-annotations", () => {
  it("groups comments by type", () => {
    const byType = commentsByType(fixture);
    expect(byType.FUNCTION).toHaveLength(2);
    expect(byType.COFACTOR).toHaveLength(1);
  });

  it("splits GO terms by aspect, parsing name + evidence", () => {
    const go = goTermsByAspect(fixture);
    expect(go.F).toHaveLength(1);
    expect(go.F[0]).toMatchObject({
      id: "GO:0016491",
      name: "oxidoreductase activity",
      aspect: "F",
      evidence: "IEA:UniProt",
    });
    expect(go.P[0].name).toBe("DNA repair");
    expect(go.C[0].name).toBe("cytoplasm");
  });

  it("groups structures by database with method/resolution; ignores non-structure xrefs", () => {
    const s = structures(fixture);
    expect(s.pdb).toHaveLength(1);
    expect(s.pdb[0]).toMatchObject({ id: "1ABC", method: "X-ray", resolution: "2.10 A" });
    expect(s.alphafold).toHaveLength(1);
    expect(s.alphafold[0].id).toBe("P12345");
    expect(s.emdb).toHaveLength(0);
  });

  it("categorizes features", () => {
    const f = featuresByCategory(fixture);
    expect(f.Sites).toHaveLength(1);
    expect(f["Secondary structure"]).toHaveLength(1);
  });

  it("handles an empty protein", () => {
    const empty = {} as unknown as Protein;
    expect(commentsByType(empty)).toEqual({});
    expect(goTermsByAspect(empty)).toEqual({ F: [], P: [], C: [] });
    expect(structures(empty)).toEqual({ pdb: [], alphafold: [], emdb: [] });
    expect(featuresByCategory(empty)).toEqual({});
  });
});
