// Personnel's fixed routes (references and filters only: never personal data).
export const PERSONNEL_HOME_PATH = "/personnel";
export const PERSONNEL_TRANSACTIONS_PATH = "/personnel/transactions";
/** The decision queue: everything waiting for this person's decision. */
export const DECISION_QUEUE_PATH = `${PERSONNEL_TRANSACTIONS_PATH}?awaiting=me`;
export const BATCHES_PATH = "/personnel/batches";
