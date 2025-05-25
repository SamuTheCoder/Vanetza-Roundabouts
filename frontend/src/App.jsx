import { useState } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from '/vite.svg'
import './App.css'
import './fixLeafletIcons';
import "leaflet/dist/leaflet.css";

import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import { Circle, Polygon } from 'react-leaflet';

export default function App() {
  return (

    <MapContainer center={[51.505, -0.09]}   zoomAnimation={false} fadeAnimation={false} zoom={13} style={{ height: '100vh', width: '100vw' }}>
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; OpenStreetMap contributors'
      />
      <Marker position={[51.505, -0.09]}>
        <Popup>Here I am!</Popup>
      </Marker>
    </MapContainer>
  );
}
