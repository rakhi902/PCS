import { TechServicesList } from "./index";
export default function Upcoming() {
  const tomorrow = new Date(); tomorrow.setDate(tomorrow.getDate() + 1); tomorrow.setHours(0, 0, 0, 0);
  return <TechServicesList title="Upcoming" params={{ date_from: tomorrow.toISOString(), status: "assigned" }} />;
}
