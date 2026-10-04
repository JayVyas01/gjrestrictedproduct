import { Button } from "@mantine/core";
import { Link } from "react-router-dom";

/** One primary action: a link to a route, or a callback. The label is already translated. */
export interface CardAction {
  label: string;
  to?: string;
  onClick?: () => void;
}

export function ActionButton({ action }: { action: CardAction }) {
  if (action.to) {
    return (
      <Button component={Link} to={action.to}>
        {action.label}
      </Button>
    );
  }
  return <Button onClick={action.onClick}>{action.label}</Button>;
}
