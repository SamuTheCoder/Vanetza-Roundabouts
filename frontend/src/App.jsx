import { useState, useEffect } from 'react';
import reactLogo from './assets/react.svg';
import viteLogo from '/vite.svg';
import './App.css';
import './fixLeafletIcons';
import "leaflet/dist/leaflet.css";

import mqtt from 'mqtt';
import { MapContainer, TileLayer, Marker } from 'react-leaflet';

export default function App() {
  const center = dmsToDecimal("40°38'29.1\"N 8°39'31.1\"W");

  const coords = [
    [-8.65897,40.64045],[-8.65893,40.64057],[-8.65882,40.64107],[-8.65876,40.64119],[-8.65863,40.64134],
    [-8.65861,40.64143],[-8.65861,40.64143],[-8.65851,40.64151],[-8.65844,40.64161],[-8.65842,40.64173],
    [-8.65845,40.64184],[-8.65852,40.64194],[-8.6586,40.642],[-8.65868,40.64204],[-8.65868,40.64204],
    [-8.65882,40.64224],[-8.65892,40.64243],[-8.65907,40.64265],[-8.65932,40.64283],[-8.65941,40.6429],
    [-8.6598,40.64322],[-8.65993,40.64332],[-8.66005,40.64341],[-8.66025,40.64354],[-8.66039,40.64365],
    [-8.66048,40.64372],[-8.66048,40.64372],[-8.66048,40.64374]
  ];

  // Flip [lng, lat] to [lat, lng]
  const markers = coords.map(([lng, lat], idx) => (
    <Marker key={idx} position={[lat, lng]} />
  ));

  useEffect(() => {
    const client = mqtt.connect('ws://192.168.98.30:8083');
  
    client.on('connect', () => {
      console.log(`[MQTT] Connected to localhost`);
      client.subscribe('#', (err) => {
        if (err) {
          console.error(`[MQTT] Subscribe error`, err);
        } else {
          console.log(`[MQTT] Subscribed to all topics`);
        }
      });
    });
  
    client.on('message', (topic, message) => {
      console.log(`[MQTT] ${topic}: ${message.toString()}`);
    });
  
    client.on('error', (err) => {
      console.error(`[MQTT] Error`, err);
    });
  
    return () => {
      client.end();
    };
  }, []);
  

  return (
    <MapContainer center={center} zoom={13} style={{ height: '100vh', width: '100vw' }}>
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; OpenStreetMap contributors'
      />
      {markers}
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
