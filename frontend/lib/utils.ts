export function cn(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

export function formatCents(amount: number) {
  return `$${(amount / 100).toFixed(2)}`;
}

export function truncateId(id: string, start = 8, end = 4) {
  if (id.length <= start + end + 3) {
    return id;
  }

  return `${id.slice(0, start)}...${id.slice(-end)}`;
}

export function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function amountToCents(amount: string) {
  const parsed = Number(amount);

  if (!Number.isFinite(parsed)) {
    return 0;
  }

  return Math.round(parsed * 100);
}

export function statusMessage(status: string, amount: number) {
  if (status === "SUCCEEDED") {
    return `Payment of ${formatCents(amount)} succeeded`;
  }

  if (status === "FAILED") {
    return "Payment declined - insufficient funds";
  }

  if (status === "TIMED_OUT") {
    return "Payment timed out - bank unreachable";
  }

  return "Payment updated";
}
