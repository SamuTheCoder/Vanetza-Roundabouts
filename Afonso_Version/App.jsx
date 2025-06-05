import { useState, useEffect, useRef } from 'react';
import './App.css';
import './fixLeafletIcons';
import "leaflet/dist/leaflet.css";

import mqtt from 'mqtt';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';

const iconColors = {
  OBU1: new L.Icon({
    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png',
    shadowUrl: 'https://unpkg.com/leaflet@1.7.1/dist/images/marker-shadow.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41]
  }),
  OBU2: new L.Icon({
    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-blue.png',
    shadowUrl: 'https://unpkg.com/leaflet@1.7.1/dist/images/marker-shadow.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41]
  }),
  OBU3: new L.Icon({
    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-green.png',
    shadowUrl: 'https://unpkg.com/leaflet@1.7.1/dist/images/marker-shadow.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41]
  }),
};


export default function App() {
  const center = dmsToDecimal("40°38'29.1\"N 8°39'31.1\"W");
  const [obuMarkers, setObuMarkers] = useState({});
  const markerRefs = useRef({});

  useEffect(() => {
    const client = mqtt.connect('ws://192.168.98.30:8083');

    client.on('connect', () => {
      console.log(`[MQTT] Connected`);
      client.subscribe('frontend/obu_position');
    });

    client.on('message', (topic, message) => {
      try {
        const data = JSON.parse(message.toString());
        const { obu_id, latitude, longitude } = data;

        if (typeof latitude === 'number' && typeof longitude === 'number') {
          const newPos = [latitude, longitude];

          // Animate if marker already exists
          if (markerRefs.current[obu_id]) {
            animateMarker(markerRefs.current[obu_id], newPos, 500);
          }

          // Trigger re-render
          setObuMarkers(prev => ({
            ...prev,
            [obu_id]: newPos
          }));
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
      {Object.entries(obuMarkers).map(([obu_id, position]) => (
        <AnimatedMarker
          key={obu_id}
          obu_id={obu_id}
          position={position}
          icon={iconColors[obu_id] || undefined}
          markerRefs={markerRefs}
        />
      ))}
    </MapContainer>
  );
}

function AnimatedMarker({ obu_id, position, icon, markerRefs }) {
  const markerRef = useRef();

  useEffect(() => {
    if (markerRef.current) {
      markerRefs.current[obu_id] = markerRef.current;
    }
  }, [markerRef, obu_id, markerRefs]);

  return (
    <Marker ref={markerRef} position={position} icon={icon}>
      <Popup>{obu_id}</Popup>
    </Marker>
  );
}

// Animate between positions
function animateMarker(marker, targetPos, duration = 500) {
  const start = marker.getLatLng();
  const end = L.latLng(targetPos);
  const steps = 30;
  let step = 0;

  const latStep = (end.lat - start.lat) / steps;
  const lngStep = (end.lng - start.lng) / steps;

  const interval = setInterval(() => {
    step++;
    if (step >= steps) {
      marker.setLatLng(end);
      clearInterval(interval);
    } else {
      const intermediate = L.latLng(
        start.lat + latStep * step,
        start.lng + lngStep * step
      );
      marker.setLatLng(intermediate);
    }
  }, duration / steps);
}

// Helper
function dmsToDecimal(dmsString) {
  const parts = dmsString.match(/(\d+)°(\d+)'([\d.]+)"?([NSEW])/gi);
  if (!parts || parts.length !== 2) throw new Error("Invalid DMS format");

  const convert = (dms) => {
    const match = dms.match(/(\d+)°(\d+)'([\d.]+)"?([NSEW])/);
    const degrees = parseFloat(match[1]);
    const minutes = parseFloat(match[2]);
    const seconds = parseFloat(match[3]);
    const direction = match[4].toUpperCase();

    let decimal = degrees + minutes / 60 + seconds / 3600;
    if (direction === 'S' || direction === 'W') decimal *= -1;
    return decimal;
  };

  return [convert(parts[0]), convert(parts[1])];
}
