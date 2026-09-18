"use client";

import { useEffect, useState } from "react";
import { MapContainer, TileLayer, Marker, useMapEvents } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";

// Fix Leaflet's default icon issue in Next.js
delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png",
  iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
});

interface MapPickerProps {
  onLocationSelect: (lat: number, lng: number) => void;
  defaultLocation?: { lat: number; lng: number };
}

function LocationMarker({ onSelect, defaultLocation }: { onSelect: (lat: number, lng: number) => void, defaultLocation: { lat: number; lng: number } | null }) {
  const [position, setPosition] = useState<L.LatLng | null>(
    defaultLocation ? new L.LatLng(defaultLocation.lat, defaultLocation.lng) : null
  );

  const map = useMapEvents({
    click(e) {
      setPosition(e.latlng);
      onSelect(e.latlng.lat, e.latlng.lng);
    },
    locationfound(e) {
      setPosition(e.latlng);
      map.flyTo(e.latlng, map.getZoom());
      onSelect(e.latlng.lat, e.latlng.lng);
    },
  });

  // Locate the user once the map loads if no default location is provided
  useEffect(() => {
    if (!defaultLocation) {
      map.locate();
    }
  }, [map, defaultLocation]);

  return position === null ? null : (
    <Marker position={position}></Marker>
  );
}

export default function MapPicker({ onLocationSelect, defaultLocation }: MapPickerProps) {
  // Center defaults to a general location (e.g., center of India) if not provided
  const center = defaultLocation || { lat: 20.5937, lng: 78.9629 };

  return (
    <div className="h-64 w-full rounded-md overflow-hidden shadow-[0_2px_8px_rgba(16,34,15,0.06)] border border-border-default/20">
      <MapContainer
        center={[center.lat, center.lng]}
        zoom={defaultLocation ? 15 : 5}
        scrollWheelZoom={true}
        style={{ height: "100%", width: "100%" }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <LocationMarker onSelect={onLocationSelect} defaultLocation={defaultLocation || null} />
      </MapContainer>
    </div>
  );
}
