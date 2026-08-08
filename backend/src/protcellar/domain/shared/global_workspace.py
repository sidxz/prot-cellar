"""The workspace that owns shared reference data."""

from __future__ import annotations

import uuid

# Reference data (organisms, genes, proteins, proteomes) is shared across tenants.
# It is owned by this workspace rather than exempted from the tenancy check, so
# every read filters and no table is special-cased.
#
# Deliberately NOT the null UUID: that value is indistinguishable from "unset", so
# a forgotten assignment would make a row readable by everyone. With a distinct id
# the same mistake makes it readable by nobody — safe, and loud enough to find.
# Value is uuid5(NAMESPACE_DNS, "shared.protcellar").
SHARED_WORKSPACE_ID: uuid.UUID = uuid.UUID("a577f0f9-b1fb-53b6-be5d-49bcb500adeb")
