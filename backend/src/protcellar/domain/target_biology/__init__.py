"""Target-biology bounded context — typed facts about a target (gene/protein).

Holds the observation records legacy DAIKON attached to its Gene god-object
(essentiality, vulnerability, CRISPRi strains, …). References genes/proteins by
bare UUID; never imports a sibling context.
"""
