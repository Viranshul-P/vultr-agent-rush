import { Composition } from "remotion";
import { AirlockDemo, totalFrames } from "./AirlockDemo";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="AirlockDemo"
        component={AirlockDemo}
        durationInFrames={totalFrames()}
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};
