// The Head Authority's and the Software Owner's read-only screens, each under the role's own base
// path (fixed paths; references and numeric IDs only).
export interface OverviewPaths {
  home: string;
  transactions: string;
  batches: string;
  reviewPeriods: string;
  licences: string;
}

function under(home: string): OverviewPaths {
  return {
    home,
    transactions: `${home}/transactions`,
    batches: `${home}/batches`,
    reviewPeriods: `${home}/review-periods`,
    licences: `${home}/licences`,
  };
}

export const HEAD_PATHS = under("/head");
export const OWNER_PATHS = under("/overview");

