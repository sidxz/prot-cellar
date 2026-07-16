"""The ingestion-plugin contract — pure application-layer shapes.

manifest/validation/sink/context/protocol are import-clean (application + domain
only) so tests and the interface layer can reference them without pulling in the
concrete infrastructure registry.
"""
