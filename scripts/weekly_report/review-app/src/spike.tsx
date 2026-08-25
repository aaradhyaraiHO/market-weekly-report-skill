import { createRoot } from "react-dom/client";
import { Button, Text, Checkbox } from "@headout/eevee";
function App() {
  return (
    <div style={{ padding: 24, fontFamily: "halyard-text, sans-serif" }}>
      <Text as="h2">Eevee native spike ✓</Text>
      <div style={{ display: "flex", gap: 12, alignItems: "center", marginTop: 16 }}>
        <Button variant="primary" btnType="primary" primaryText="Real Eevee Button" onClick={() => console.log("native click")} />
        <Button variant="secondary" btnType="black" primaryText="Secondary" />
        <Button variant="tertiary" btnType="transparent" primaryText="Tertiary" />
      </div>
    </div>
  );
}
createRoot(document.getElementById("review-view") || document.body).render(<App />);
