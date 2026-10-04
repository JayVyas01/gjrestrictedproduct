// Rule changes' fixed routes (numeric IDs only), shared by every role that sees them.
export const RULE_CHANGES_PATH = "/rule-changes";
export const NEW_RULE_CHANGE_PATH = "/rule-changes/new";

export function ruleChangePath(id: number): string {
  return `${RULE_CHANGES_PATH}/${id}`;
}
