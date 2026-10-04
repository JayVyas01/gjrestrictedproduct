// The licensee's fixed routes (references and filters only: never personal data).
export const LICENSEE_HOME_PATH = "/licensee";
export const TRANSACTIONS_PATH = "/licensee/transactions";
/** The home page's link to the purchases waiting for the licensee. */
export const AWAITING_PURCHASES_PATH = `${TRANSACTIONS_PATH}?side=purchases&awaiting=me`;
export const NEW_SALE_PATH = "/licensee/sale/new";
