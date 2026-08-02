/* Generated from brief_block.schema.json. Do not edit manually. */

export type CitationIds = string[];
export type Provenance = string;
export type Text = string;

/**
 * One rendered line/element within a brief section, carrying provenance.
 */
export interface BriefBlock {
  citation_ids?: CitationIds;
  provenance: Provenance;
  text: Text;
}
