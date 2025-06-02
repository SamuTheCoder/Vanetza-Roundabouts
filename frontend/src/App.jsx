import { useState, useEffect } from 'react';
import './App.css';
import './fixLeafletIcons';
import "leaflet/dist/leaflet.css";

import mqtt from 'mqtt';
import { MapContainer, TileLayer, Marker } from 'react-leaflet';

export default function App() {
  const center = dmsToDecimal("40°38'29.1\"N 8°39'31.1\"W");
  const [currentMarker, setCurrentMarker] = useState(null); // only one marker now

  useEffect(() => {
    const client = mqtt.connect('ws://192.168.98.30:8083');

    client.on('connect', () => {
      console.log(`[MQTT] Connected`);
      client.subscribe('#');
    });

    client.on('message', (topic, message) => {
      try {
        const data = JSON.parse(message.toString());
        const lat = data.fields?.cam?.camParameters?.basicContainer?.referencePosition?.latitude;
        const lng = data.fields?.cam?.camParameters?.basicContainer?.referencePosition?.longitude;

        if (typeof lat === 'number' && typeof lng === 'number') {
          setCurrentMarker([lat, lng]); // just update with latest marker
        }

      } catch (err) {
        console.error(`[MQTT] Parse error`, err);
      }
    });

    return () => client.end();
  }, []);

  return (
    <MapContainer center={center} zoom={15} style={{ height: '100vh', width: '100vw' }}>
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; OpenStreetMap contributors'
      />
      {currentMarker && <Marker position={currentMarker} />}
    </MapContainer>
  );
}

function dmsToDecimal(dmsString) {
  const parts = dmsString.match(/(\d+)°(\d+)'([\d.]+)"?([NSEW])/gi);

  if (!parts || parts.length !== 2) {
    throw new Error("Invalid DMS coordinate format. Expected 2 components (lat, lng).");
  }

  const convert = (dms) => {
    const match = dms.match(/(\d+)°(\d+)'([\d.]+)"?([NSEW])/);
    if (!match) throw new Error("Invalid DMS component.");

    const degrees = parseFloat(match[1]);
    const minutes = parseFloat(match[2]);
    const seconds = parseFloat(match[3]);
    const direction = match[4].toUpperCase();

    let decimal = degrees + minutes / 60 + seconds / 3600;

    if (direction === 'S' || direction === 'W') {
      decimal *= -1;
    }

    return decimal;
  };

  const lat = convert(parts[0]);
  const lng = convert(parts[1]);

  return [lat, lng];
}

