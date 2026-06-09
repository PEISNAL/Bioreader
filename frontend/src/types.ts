/** BioReader shared types — clean slate for v5 */
export interface SectionPara { en?: string; zh?: string; refs?: string[] }
export interface Section { slug: string; title: string; paragraphs: SectionPara[] }
export interface Figure { id: string; caption: string; page: number }
export interface ParseResponse {
  file_path?: string; parse_time_ms?: number
  sections: Section[]; figures: Figure[]; references: string[]
}
