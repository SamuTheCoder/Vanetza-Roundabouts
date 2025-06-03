// App.jsx or App.tsx

import { useState, useEffect } from 'react';
import './App.css';
import './fixLeafletIcons';
import "leaflet/dist/leaflet.css";

import mqtt from 'mqtt';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';

// Marker icons per OBU
const iconColors = {
  OBU1: new L.Icon({
    iconUrl: 'https://chart.googleapis.com/chart?chst=d_map_pin_letter&chld=1|ff0000',
    iconSize: [21, 34],
    iconAnchor: [10, 34],
  }),
  OBU2: new L.Icon({
    iconUrl: 'https://chart.googleapis.com/chart?chst=d_map_pin_letter&chld=2|0000ff',
    iconSize: [21, 34],
    iconAnchor: [10, 34],
  }),
};

export default function App() {
  const center = dmsToDecimal("40°38'29.1\"N 8°39'31.1\"W");
  const [obuMarkers, setObuMarkers] = useState({});

  useEffect(() => {
    const client = mqtt.connect('ws://192.168.98.30:8083');

    client.on('connect', () => {
      console.log('[MQTT] Connected');
      client.subscribe('frontend/obu_position');
    });

    client.on('message', (topic, message) => {
      try {
        const data = JSON.parse(message.toString());
        const { obu_id, latitude, longitude } = data;

        if (typeof latitude === 'number' && typeof longitude === 'number') {
          setObuMarkers(prev => ({
            ...prev,
            [obu_id]: [latitude, longitude]
          }));
        }
      } catch (err) {
        console.error('[MQTT] Parse error', err);
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
      {Object.entries(obuMarkers).map(([obu_id, position]) => (
        <Marker key={obu_id} position={position} icon={iconColors[obu_id] || undefined}>
          <Popup>{obu_id}</Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}

function dmsToDecimal(dmsString) {
  const parts = dmsString.match(/(\d+)°(\d+)'([\d.]+)"?([NSEW])/gi);
  if (!parts || parts.length !== 2) {
    throw new Error("Invalid DMS format.");
  }

  const convert = (dms) => {
    const match = dms.match(/(\d+)°(\d+)'([\d.]+)"?([NSEW])/);
    const degrees = parseFloat(match[1]);
    const minutes = parseFloat(match[2]);
    const seconds = parseFloat(match[3]);
    const direction = match[4];

    let decimal = degrees + minutes / 60 + seconds / 3600;
    if (['S', 'W'].includes(direction)) decimal *= -1;
    return decimal;
  };

  const lat = convert(parts[0]);
  const lng = convert(parts[1]);
  return [lat, lng];
}
