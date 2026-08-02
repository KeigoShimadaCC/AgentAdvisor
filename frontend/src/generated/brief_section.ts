/* Generated from brief_section.schema.json. Do not edit manually. */

export type CitationIds = string[];
export type Provenance = string;
export type Text = string;
export type Blocks = BriefBlock[];
export type Key = string;
export type Status = 'pending' | 'partial' | 'final' | 'not_assessed';

export interface BriefSection {
  blocks?: Blocks;
  key: Key;
  status: Status;
}
/**
 * One rendered line/element within a brief section, carrying provenance.
 */
export interface BriefBlock {
  citation_ids?: CitationIds;
  provenance: Provenance;
  text: Text;
}
