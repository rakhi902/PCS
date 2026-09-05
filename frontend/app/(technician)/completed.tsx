import { TechServicesList } from "./index";
export default function Completed() {
  return <TechServicesList title="Completed" params={{ status: "completed" }} />;
}
