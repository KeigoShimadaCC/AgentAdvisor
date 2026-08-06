import { SourcesRoom } from "../rooms/Sources/SourcesRoom";
import { AssumptionsRoom } from "../rooms/Assumptions/AssumptionsRoom";
import { OptionsRoom } from "../rooms/Options/OptionsRoom";
import { ChallengesRoom } from "../rooms/Challenges/ChallengesRoom";
import { PlanRoom } from "../rooms/Plan/PlanRoom";
import { MethodRoom } from "../rooms/Method/MethodRoom";
import { ROOMS, type RoomKey } from "../../copy/terms";

const ROOM_COMPONENTS: Record<RoomKey, () => React.JSX.Element> = {
  sources: SourcesRoom,
  assumptions: AssumptionsRoom,
  options: OptionsRoom,
  challenges: ChallengesRoom,
  plan: PlanRoom,
  method: MethodRoom,
};

export function isRoomKey(value: string | undefined): value is RoomKey {
  return value !== undefined && value in ROOMS;
}

/** Renders one room's body into the case surface's context panel (SPEC-048). */
export function RoomPanel({ room }: { room: RoomKey }) {
  const Room = ROOM_COMPONENTS[room];
  return <Room />;
}
