import SwiftUI
import HealthKit
import Foundation
import Network



// MARK: - Content View
struct ContentView: View {
    @StateObject private var healthManager = HealthKitService.shared
    @StateObject private var dataTransmitter = DataTransmitter()
    @State private var isMonitoring = false
    @State private var currentGaitData: GaitData?
    @State private var showingSettings = false
    @State private var patientID = ""
    
    var body: some View {
        NavigationView {
            VStack(spacing: 20) {
                // Patient ID Input
                if patientID.isEmpty {
                    PatientSetupView(patientID: $patientID)
                } else {
                    // Status Section
                    StatusCardView(
                        patientID: patientID,
                        isConnected: dataTransmitter.isConnected,
                        isMonitoring: isMonitoring,
                        lastUpdate: currentGaitData?.timestamp
                    )
                    
                    // Current Gait Metrics (MS-specific)
                    if let gaitData = currentGaitData {
                        MSGaitMetricsView(gaitData: gaitData)
                    }
                    
                    // Control Buttons
                    VStack(spacing: 15) {
                        Button(action: {
                            if isMonitoring {
                                stopMonitoring()
                            } else {
                                startMonitoring()
                            }
                        }) {
                            Text(isMonitoring ? "Stop Monitoring" : "Start Monitoring")
                                .font(.headline)
                                .foregroundColor(.white)
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(isMonitoring ? Color.red : Color.blue)
                                .cornerRadius(10)
                        }
                        
                        HStack(spacing: 10) {
                            Button("Send Historical Data") {
                                sendHistoricalData()
                            }
                            .font(.subheadline)
                            .foregroundColor(.blue)
                            .padding()
                            .overlay(
                                RoundedRectangle(cornerRadius: 10)
                                    .stroke(Color.blue, lineWidth: 1)
                            )
                            
                            Button("Export XML") {
                                exportHealthXML()
                            }
                            .font(.subheadline)
                            .foregroundColor(.green)
                            .padding()
                            .overlay(
                                RoundedRectangle(cornerRadius: 10)
                                    .stroke(Color.green, lineWidth: 1)
                            )
                        }
                    }
                    
                    // Quick Status Indicators
                    MSStatusIndicators(gaitData: currentGaitData)
                }
                
                Spacer()
            }
            .padding()
            .navigationTitle("MS Gait Tracker")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                Button("Settings") {
                    showingSettings = true
                }
            }
            .sheet(isPresented: $showingSettings) {
                SettingsView(dataTransmitter: dataTransmitter)
            }
            .onAppear {
                healthManager.requestAuthorization()
                if !patientID.isEmpty {
                    dataTransmitter.connect(patientID: patientID)
                }
            }
        }
    }
    
    private func startMonitoring() {
        isMonitoring = true
        healthManager.startRealTimeMonitoring { gaitData in
            DispatchQueue.main.async {
                self.currentGaitData = gaitData
                self.dataTransmitter.sendRealTimeData(gaitData, patientID: self.patientID)
            }
        }
    }
    
    private func stopMonitoring() {
        isMonitoring = false
        healthManager.stopRealTimeMonitoring()
    }
    
    private func sendHistoricalData() {
        healthManager.fetchHistoricalGaitData { historicalData in
            self.dataTransmitter.sendHistoricalData(historicalData, patientID: self.patientID)
        }
    }
    
    private func exportHealthXML() {
        healthManager.exportToXML(patientID: patientID) { success in
            DispatchQueue.main.async {
                // Show success/failure message
            }
        }
    }
}

// MARK: - MS-Specific Gait Data Model
struct GaitData: Codable, Identifiable {
    var id = UUID()
    let timestamp: Date
    let walkingSpeed: Double?           // m/s - Critical for MS
    let stepLength: Double?             // m - Reduced in MS
    let walkingAsymmetry: Double?       // % - Higher in MS
    let doubleSupportTime: Double?      // % - Increased in MS
    let stepCount: Int?
    let stepCadence: Double?            // steps/min
    let sixMinuteWalkDistance: Double?  // Common MS assessment
    
    // MS-specific calculated metrics
    var speedCategory: String {
        guard let speed = walkingSpeed else { return "Unknown" }
        if speed < 0.8 { return "Severely Impaired" }
        if speed < 1.0 { return "Mildly Impaired" }
        if speed < 1.3 { return "Normal" }
        return "Above Average"
    }
    
    var asymmetryAlert: Bool {
        guard let asymmetry = walkingAsymmetry else { return false }
        return asymmetry > 10.0 // MS threshold
    }
    
    var doubleSupportAlert: Bool {
        guard let doubleSupport = doubleSupportTime else { return false }
        return doubleSupport > 30.0 // MS threshold
    }
    
    var xmlRecord: String {
        let formatter = ISO8601DateFormatter()
        let dateStr = formatter.string(from: timestamp)
        
        var xml = ""
        
        if let walkingSpeed = walkingSpeed {
            xml += """
            <Record type="HKQuantityTypeIdentifierWalkingSpeed" sourceName="MSGaitTracker" sourceVersion="1.0" device="&lt;&lt;HKDevice: 0x123&gt;&gt;" unit="m/s" creationDate="\(dateStr)" startDate="\(dateStr)" endDate="\(dateStr)" value="\(walkingSpeed)"/>
            """
        }
        
        if let stepLength = stepLength {
            xml += """
            <Record type="HKQuantityTypeIdentifierStepLength" sourceName="MSGaitTracker" sourceVersion="1.0" device="&lt;&lt;HKDevice: 0x123&gt;&gt;" unit="m" creationDate="\(dateStr)" startDate="\(dateStr)" endDate="\(dateStr)" value="\(stepLength)"/>
            """
        }
        
        if let walkingAsymmetry = walkingAsymmetry {
            xml += """
            <Record type="HKQuantityTypeIdentifierWalkingAsymmetryPercentage" sourceName="MSGaitTracker" sourceVersion="1.0" device="&lt;&lt;HKDevice: 0x123&gt;&gt;" unit="%" creationDate="\(dateStr)" startDate="\(dateStr)" endDate="\(dateStr)" value="\(walkingAsymmetry)"/>
            """
        }
        
        if let doubleSupportTime = doubleSupportTime {
            xml += """
            <Record type="HKQuantityTypeIdentifierWalkingDoubleSupportPercentage" sourceName="MSGaitTracker" sourceVersion="1.0" device="&lt;&lt;HKDevice: 0x123&gt;&gt;" unit="%" creationDate="\(dateStr)" startDate="\(dateStr)" endDate="\(dateStr)" value="\(doubleSupportTime)"/>
            """
        }
        
        return xml
    }
    
    var dictionary: [String: Any] {
        return [
            "patient_id": "", // Will be set by transmitter
            "timestamp": ISO8601DateFormatter().string(from: timestamp),
            "walking_speed": walkingSpeed ?? NSNull(),
            "step_length": stepLength ?? NSNull(),
            "walking_asymmetry": walkingAsymmetry ?? NSNull(),
            "double_support_time": doubleSupportTime ?? NSNull(),
            "step_count": stepCount ?? NSNull(),
            "step_cadence": stepCadence ?? NSNull(),
            "six_minute_walk_distance": sixMinuteWalkDistance ?? NSNull(),
            "speed_category": speedCategory,
            "asymmetry_alert": asymmetryAlert,
            "double_support_alert": doubleSupportAlert
        ]
    }
}

// MARK: - Patient Setup View
struct PatientSetupView: View {
    @Binding var patientID: String
    @State private var tempPatientID = ""
    
    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "person.badge.plus")
                .font(.system(size: 60))
                .foregroundColor(.blue)
            
            Text("MS Gait Tracker Setup")
                .font(.title)
                .fontWeight(.semibold)
            
            Text("Enter a unique patient identifier to begin monitoring gait data for MS analysis.")
                .multilineTextAlignment(.center)
                .foregroundColor(.secondary)
            
            TextField("Patient ID (e.g., MS001)", text: $tempPatientID)
                .textFieldStyle(RoundedBorderTextFieldStyle())
                .autocapitalization(.allCharacters)
            
            Button("Start Tracking") {
                patientID = tempPatientID.trimmingCharacters(in: .whitespacesAndNewlines)
            }
            .font(.headline)
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .padding()
            .background(tempPatientID.isEmpty ? Color.gray : Color.blue)
            .cornerRadius(10)
            .disabled(tempPatientID.isEmpty)
        }
        .padding()
    }
}

// MARK: - Enhanced HealthKit Manager
class HealthKitManager: ObservableObject, HealthKitManaging {
    private let healthStore = HKHealthStore()
    private var gaitDataCallback: ((GaitData) -> Void)?
    private var timer: Timer?
    
    // MS-specific HealthKit sample types
    private let msGaitTypes: Set<HKSampleType> = [
        HKQuantityType.quantityType(forIdentifier: .walkingSpeed)!,
        HKQuantityType.quantityType(forIdentifier: .walkingStepLength)!,
        HKQuantityType.quantityType(forIdentifier: .walkingAsymmetryPercentage)!,
        HKQuantityType.quantityType(forIdentifier: .walkingDoubleSupportPercentage)!,
        HKQuantityType.quantityType(forIdentifier: .stepCount)!,
        HKQuantityType.quantityType(forIdentifier: .sixMinuteWalkTestDistance)!
    ]
    
    func requestAuthorization() {
        guard HKHealthStore.isHealthDataAvailable() else {
            print("HealthKit not available")
            return
        }
        
        healthStore.requestAuthorization(toShare: [], read: msGaitTypes) { success, error in
            if success {
                print("HealthKit authorization granted")
                DispatchQueue.main.async {
                    self.setupBackgroundDelivery()
                }
            } else {
                print("HealthKit authorization failed: \(error?.localizedDescription ?? "Unknown error")")
            }
        }
    }
    
    func startRealTimeMonitoring(callback: @escaping (GaitData) -> Void) {
        self.gaitDataCallback = callback
        
        // Poll for new data every 30 seconds (good for MS monitoring)
        timer = Timer.scheduledTimer(withTimeInterval: 30.0, repeats: true) { _ in
            self.fetchLatestGaitData()
        }
        
        // Fetch initial data
        fetchLatestGaitData()
    }
    
    func stopRealTimeMonitoring() {
        timer?.invalidate()
        timer = nil
        gaitDataCallback = nil
    }
    
    private func fetchLatestGaitData() {
        let now = Date()
        let oneMinuteAgo = Calendar.current.date(byAdding: .minute, value: -1, to: now)!
        
        fetchAggregatedGaitData(from: oneMinuteAgo, to: now) { gaitData in
            if let data = gaitData {
                self.gaitDataCallback?(data)
            }
        }
    }
    
    func fetchHistoricalGaitData(completion: @escaping ([GaitData]) -> Void) {
        let endDate = Date()
        let startDate = Calendar.current.date(byAdding: .day, value: -90, to: endDate)! // Last 90 days for MS trend analysis
        
        fetchDailyGaitData(from: startDate, to: endDate, completion: completion)
    }
    
    private func fetchDailyGaitData(from startDate: Date, to endDate: Date, completion: @escaping ([GaitData]) -> Void) {
        let calendar = Calendar.current
        var gaitDataArray: [GaitData] = []
        let group = DispatchGroup()
        
        // Iterate through each day
        var currentDate = startDate
        while currentDate <= endDate {
            let dayStart = calendar.startOfDay(for: currentDate)
            let dayEnd = calendar.date(byAdding: .day, value: 1, to: dayStart)!
            
            group.enter()
            fetchAggregatedGaitData(from: dayStart, to: dayEnd) { dailyGaitData in
                if let data = dailyGaitData {
                    gaitDataArray.append(data)
                }
                group.leave()
            }
            
            currentDate = calendar.date(byAdding: .day, value: 1, to: currentDate)!
        }
        
        group.notify(queue: .main) {
            completion(gaitDataArray.sorted { $0.timestamp < $1.timestamp })
        }
    }
    
    private func fetchAggregatedGaitData(from startDate: Date, to endDate: Date, completion: @escaping (GaitData?) -> Void) {
        let group = DispatchGroup()
        var gaitBuilder = GaitDataBuilder(timestamp: startDate)
        
        // Fetch each metric
        group.enter()
        fetchAverageQuantity(for: .walkingSpeed, from: startDate, to: endDate) { value in
            gaitBuilder.walkingSpeed = value
            group.leave()
        }
        
        group.enter()
        fetchAverageQuantity(for: .walkingStepLength, from: startDate, to: endDate) { value in
            gaitBuilder.stepLength = value
            group.leave()
        }
        
        group.enter()
        fetchAverageQuantity(for: .walkingAsymmetryPercentage, from: startDate, to: endDate) { value in
            gaitBuilder.walkingAsymmetry = value
            group.leave()
        }
        
        group.enter()
        fetchAverageQuantity(for: .walkingDoubleSupportPercentage, from: startDate, to: endDate) { value in
            gaitBuilder.doubleSupportTime = value
            group.leave()
        }
        
        group.enter()
        fetchSumQuantity(for: .stepCount, from: startDate, to: endDate) { value in
            gaitBuilder.stepCount = Int(value ?? 0)
            group.leave()
        }
        
        group.notify(queue: .main) {
            completion(gaitBuilder.build())
        }
    }
    
    private func fetchAverageQuantity(for identifier: HKQuantityTypeIdentifier, from startDate: Date, to endDate: Date, completion: @escaping (Double?) -> Void) {
        guard let quantityType = HKQuantityType.quantityType(forIdentifier: identifier) else {
            completion(nil)
            return
        }
        
        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: endDate, options: .strictStartDate)
        let query = HKSampleQuery(sampleType: quantityType, predicate: predicate, limit: HKObjectQueryNoLimit, sortDescriptors: nil) { _, samples, error in
            
            guard let samples = samples as? [HKQuantitySample], error == nil, !samples.isEmpty else {
                completion(nil)
                return
            }
            
            let unit = self.getUnit(for: identifier)
            let values = samples.map { $0.quantity.doubleValue(for: unit) }
            let average = values.reduce(0, +) / Double(values.count)
            
            completion(average)
        }
        
        healthStore.execute(query)
    }
    
    private func fetchSumQuantity(for identifier: HKQuantityTypeIdentifier, from startDate: Date, to endDate: Date, completion: @escaping (Double?) -> Void) {
        guard let quantityType = HKQuantityType.quantityType(forIdentifier: identifier) else {
            completion(nil)
            return
        }
        
        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: endDate, options: .strictStartDate)
        let query = HKSampleQuery(sampleType: quantityType, predicate: predicate, limit: HKObjectQueryNoLimit, sortDescriptors: nil) { _, samples, error in
            
            guard let samples = samples as? [HKQuantitySample], error == nil else {
                completion(nil)
                return
            }
            
            let unit = self.getUnit(for: identifier)
            let sum = samples.reduce(0) { $0 + $1.quantity.doubleValue(for: unit) }
            
            completion(sum)
        }
        
        healthStore.execute(query)
    }
    
    private func getUnit(for identifier: HKQuantityTypeIdentifier) -> HKUnit {
        switch identifier {
        case .walkingSpeed:
            return HKUnit.meter().unitDivided(by: HKUnit.second())
        case .walkingStepLength:
            return HKUnit.meter()
        case .walkingAsymmetryPercentage, .walkingDoubleSupportPercentage:
            return HKUnit.percent()
        case .stepCount:
            return HKUnit.count()
        case .sixMinuteWalkTestDistance:
            return HKUnit.meter()
        default:
            return HKUnit.count()
        }
    }
    
    func exportToXML(patientID: String, completion: @escaping (Bool) -> Void) {
        fetchHistoricalGaitData { gaitDataArray in
            let xmlContent = self.generateXMLExport(gaitDataArray: gaitDataArray, patientID: patientID)
            self.saveXMLFile(content: xmlContent, patientID: patientID, completion: completion)
        }
    }
    
    private func generateXMLExport(gaitDataArray: [GaitData], patientID: String) -> String {
        let header = """
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE HealthData [
        <!ELEMENT HealthData (ExportDate|Record)*>
        <!ELEMENT Record EMPTY>
        <!ATTLIST Record
            type CDATA #REQUIRED
            sourceName CDATA #IMPLIED
            sourceVersion CDATA #IMPLIED
            device CDATA #IMPLIED
            unit CDATA #IMPLIED
            creationDate CDATA #IMPLIED
            startDate CDATA #IMPLIED
            endDate CDATA #IMPLIED
            value CDATA #IMPLIED
        >
        ]>
        <HealthData locale="en_US">
        <ExportDate value="\(ISO8601DateFormatter().string(from: Date()))"/>
        """
        
        let records = gaitDataArray.map { $0.xmlRecord }.joined(separator: "\n")
        let footer = "</HealthData>"
        
        return header + "\n" + records + "\n" + footer
    }
    
    private func saveXMLFile(content: String, patientID: String, completion: @escaping (Bool) -> Void) {
        let fileName = "\(patientID)_gait_export_\(Int(Date().timeIntervalSince1970)).xml"
        let documentsPath = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let fileURL = documentsPath.appendingPathComponent(fileName)
        
        do {
            try content.write(to: fileURL, atomically: true, encoding: .utf8)
            print("XML exported to: \(fileURL)")
            completion(true)
        } catch {
            print("Failed to save XML: \(error)")
            completion(false)
        }
    }
    
    private func setupBackgroundDelivery() {
        for type in msGaitTypes {
            healthStore.enableBackgroundDelivery(for: type, frequency: .immediate) { success, error in
                if !success {
                    print("Background delivery setup failed for \(type): \(error?.localizedDescription ?? "")")
                }
            }
        }
    }
}

// MARK: - Gait Data Builder Helper
struct GaitDataBuilder {
    let timestamp: Date
    var walkingSpeed: Double?
    var stepLength: Double?
    var walkingAsymmetry: Double?
    var doubleSupportTime: Double?
    var stepCount: Int?
    var stepCadence: Double?
    var sixMinuteWalkDistance: Double?
    
    func build() -> GaitData {
        return GaitData(
            timestamp: timestamp,
            walkingSpeed: walkingSpeed,
            stepLength: stepLength,
            walkingAsymmetry: walkingAsymmetry,
            doubleSupportTime: doubleSupportTime,
            stepCount: stepCount,
            stepCadence: stepCadence,
            sixMinuteWalkDistance: sixMinuteWalkDistance
        )
    }
}

// MARK: - Enhanced Data Transmitter
class DataTransmitter: ObservableObject {
    @Published var isConnected = false
    @Published var serverURL = "wss://your-streamlit-server.com/ws"
    private var webSocketTask: URLSessionWebSocketTask?
    
    func connect(patientID: String) {
        guard let url = URL(string: "\(serverURL)?patient_id=\(patientID)") else { return }
        
        webSocketTask = URLSession.shared.webSocketTask(with: url)
        webSocketTask?.resume()
        
        receiveMessage()
        
        DispatchQueue.main.async {
            self.isConnected = true
        }
    }
    
    func sendRealTimeData(_ gaitData: GaitData, patientID: String) {
        var dataDict = gaitData.dictionary
        dataDict["patient_id"] = patientID
        dataDict["data_type"] = "real_time"
        
        sendData(dataDict)
    }
    
    func sendHistoricalData(_ historicalData: [GaitData], patientID: String) {
        let payload: [String: Any] = [
            "patient_id": patientID,
            "data_type": "historical",
            "records": historicalData.map { gaitData in
                var dict = gaitData.dictionary
                dict["patient_id"] = patientID
                return dict
            }
        ]
        
        sendData(payload)
    }
    
    private func sendData(_ data: [String: Any]) {
        guard let jsonData = try? JSONSerialization.data(withJSONObject: data),
              let jsonString = String(data: jsonData, encoding: .utf8) else {
            return
        }
        
        let message = URLSessionWebSocketTask.Message.string(jsonString)
        webSocketTask?.send(message) { error in
            if let error = error {
                print("WebSocket send error: \(error)")
            }
        }
    }
    
    private func receiveMessage() {
        webSocketTask?.receive { result in
            switch result {
            case .success(let message):
                switch message {
                case .string(let text):
                    print("Server response: \(text)")
                case .data(let data):
                    print("Received binary data: \(data)")
                @unknown default:
                    break
                }
                self.receiveMessage()
            case .failure(let error):
                print("WebSocket receive error: \(error)")
                DispatchQueue.main.async {
                    self.isConnected = false
                }
            }
        }
    }
    
    func disconnect() {
        webSocketTask?.cancel(with: .goingAway, reason: nil)
        DispatchQueue.main.async {
            self.isConnected = false
        }
    }
}

// MARK: - MS-Specific UI Components
struct StatusCardView: View {
    let patientID: String
    let isConnected: Bool
    let isMonitoring: Bool
    let lastUpdate: Date?
    
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Patient: \(patientID)")
                    .font(.headline)
                Spacer()
                Circle()
                    .fill(isConnected ? Color.green : Color.red)
                    .frame(width: 12, height: 12)
            }
            
            HStack {
                Text("Monitoring:")
                Text(isMonitoring ? "Active" : "Stopped")
                    .foregroundColor(isMonitoring ? .green : .orange)
                Spacer()
            }
            
            if let lastUpdate = lastUpdate {
                HStack {
                    Text("Last Update:")
                    Text(lastUpdate, style: .time)
                    Spacer()
                }
                .font(.caption)
                .foregroundColor(.secondary)
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(10)
    }
}

struct MSGaitMetricsView: View {
    let gaitData: GaitData
    
    var body: some View {
        VStack(alignment: .leading, spacing: 15) {
            Text("MS Gait Assessment")
                .font(.headline)
                .padding(.bottom, 5)
            
            // Critical MS metrics first
            LazyVGrid(columns: [
                GridItem(.flexible()),
                GridItem(.flexible())
            ], spacing: 15) {
                
                MSMetricCard(
                    title: "Walking Speed",
                    value: String(format: "%.2f", gaitData.walkingSpeed ?? 0),
                    unit: "m/s",
                    status: getSpeedStatus(gaitData.walkingSpeed),
                    isAlert: (gaitData.walkingSpeed ?? 0) < 0.8
                )
                
                MSMetricCard(
                    title: "Step Length",
                    value: String(format: "%.2f", gaitData.stepLength ?? 0),
                    unit: "m",
                    status: getStepLengthStatus(gaitData.stepLength),
                    isAlert: (gaitData.stepLength ?? 0) < 0.6
                )
                
                MSMetricCard(
                    title: "Asymmetry",
                    value: String(format: "%.1f", gaitData.walkingAsymmetry ?? 0),
                    unit: "%",
                    status: getAsymmetryStatus(gaitData.walkingAsymmetry),
                    isAlert: gaitData.asymmetryAlert
                )
                
                MSMetricCard(
                    title: "Double Support",
                    value: String(format: "%.1f", gaitData.doubleSupportTime ?? 0),
                    unit: "%",
                    status: getDoubleSupportStatus(gaitData.doubleSupportTime),
                    isAlert: gaitData.doubleSupportAlert
                )
            }
            
            // Overall assessment
            HStack {
                Text("Overall Status:")
                    .font(.subheadline)
                Text(gaitData.speedCategory)
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .foregroundColor(getStatusColor(gaitData.speedCategory))
                Spacer()
            }
            .padding(.top, 10)
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(15)
        .shadow(radius: 2)
    }
    
    private func getSpeedStatus(_ speed: Double?) -> String {
        guard let speed = speed else { return "No Data" }
        if speed < 0.8 { return "Severely Impaired" }
        if speed < 1.0 { return "Mildly Impaired" }
        return "Normal"
    }
    
    private func getStepLengthStatus(_ length: Double?) -> String {
        guard let length = length else { return "No Data" }
        if length < 0.6 { return "Reduced" }
        return "Normal"
    }
    
    private func getAsymmetryStatus(_ asymmetry: Double?) -> String {
        guard let asymmetry = asymmetry else { return "No Data" }
        if asymmetry > 10 { return "High" }
        if asymmetry > 5 { return "Moderate" }
        return "Normal"
    }
    
    private func getDoubleSupportStatus(_ doubleSupport: Double?) -> String {
        guard let doubleSupport = doubleSupport else { return "No Data" }
        if doubleSupport > 30 { return "Elevated" }
        return "Normal"
    }
    
    private func getStatusColor(_ status: String) -> Color {
        switch status {
        case "Severely Impaired", "High", "Elevated":
            return .red
        case "Mildly Impaired", "Moderate", "Reduced":
            return .orange
        default:
            return .green
        }
    }
}

struct MSMetricCard: View {
    let title: String
    let value: String
    let unit: String
    let status: String
    let isAlert: Bool
    
    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack {
                Text(title)
                    .font(.caption)
                    .foregroundColor(.secondary)
                Spacer()
                if isAlert {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundColor(.red)
                        .font(.caption)
                }
            }
            
            HStack(alignment: .lastTextBaseline, spacing: 2) {
                Text(value)
                    .font(.title3)
                    .fontWeight(.semibold)
                Text(unit)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Text(status)
                .font(.caption)
                .foregroundColor(isAlert ? .red : .green)
                .fontWeight(.medium)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(isAlert ? Color.red.opacity(0.1) : Color(.systemGray6))
        .cornerRadius(8)
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(isAlert ? Color.red.opacity(0.3) : Color.clear, lineWidth: 1)
        )
    }
}

struct MSStatusIndicators: View {
    let gaitData: GaitData?
    
    var body: some View {
        if let data = gaitData {
            VStack(spacing: 10) {
                Text("MS Alert Indicators")
                    .font(.subheadline)
                    .fontWeight(.medium)
                
                HStack(spacing: 15) {
                    AlertIndicator(
                        title: "Speed",
                        isAlert: (data.walkingSpeed ?? 0) < 0.8,
                        message: "Walking speed below MS threshold"
                    )
                    
                    AlertIndicator(
                        title: "Asymmetry",
                        isAlert: data.asymmetryAlert,
                        message: "High gait asymmetry detected"
                    )
                    
                    AlertIndicator(
                        title: "Support",
                        isAlert: data.doubleSupportAlert,
                        message: "Increased double support time"
                    )
                }
            }
            .padding()
            .background(Color(.systemGray6))
            .cornerRadius(10)
        }
    }
}

struct AlertIndicator: View {
    let title: String
    let isAlert: Bool
    let message: String
    
    var body: some View {
        VStack(spacing: 5) {
            Image(systemName: isAlert ? "exclamationmark.triangle.fill" : "checkmark.circle.fill")
                .foregroundColor(isAlert ? .red : .green)
                .font(.title2)
            
            Text(title)
                .font(.caption)
                .fontWeight(.medium)
        }
        .frame(maxWidth: .infinity)
        .onTapGesture {
            if isAlert {
                // Could show detailed message
            }
        }
    }
}

// MARK: - Settings View
struct SettingsView: View {
    @ObservedObject var dataTransmitter: DataTransmitter
    @State private var tempServerURL: String = ""
    @State private var updateInterval = 30.0
    @State private var enableNotifications = true
    @State private var dataRetentionDays = 90
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        NavigationView {
            Form {
                Section("Server Configuration") {
                    VStack(alignment: .leading, spacing: 5) {
                        Text("Server URL")
                            .font(.headline)
                        TextField("wss://your-server.com/ws", text: $tempServerURL)
                            .textFieldStyle(RoundedBorderTextFieldStyle())
                            .autocapitalization(.none)
                            .disableAutocorrection(true)
                        Text("WebSocket endpoint for real-time data streaming")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    
                    HStack {
                        Text("Update Interval")
                        Spacer()
                        Text("\(Int(updateInterval))s")
                    }
                    Slider(value: $updateInterval, in: 10...300, step: 10)
                    Text("How often to check for new gait data")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Section("MS-Specific Settings") {
                    HStack {
                        Text("Data Retention")
                        Spacer()
                        Text("\(dataRetentionDays) days")
                    }
                    Slider(value: Binding(
                        get: { Double(dataRetentionDays) },
                        set: { dataRetentionDays = Int($0) }
                    ), in: 30...365, step: 30)
                    
                    Toggle("Enable Flare Notifications", isOn: $enableNotifications)
                    Text("Alert when gait metrics suggest possible MS flare")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Section("Data Management") {
                    Button("Test Connection") {
                        testConnection()
                    }
                    
                    Button("Export Data for Analysis") {
                        // Implement data export compatible with your Python script
                    }
                    
                    Button("Clear Local Cache") {
                        // Implement cache clearing
                    }
                    .foregroundColor(.red)
                }
                
                Section("Integration Info") {
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Python Integration")
                            .font(.headline)
                        
                        Text("This app sends data in the same format as your Apple Health XML export:")
                            .font(.subheadline)
                        
                        VStack(alignment: .leading, spacing: 5) {
                            Text("• HKQuantityTypeIdentifierWalkingSpeed")
                            Text("• HKQuantityTypeIdentifierStepLength")
                            Text("• HKQuantityTypeIdentifierWalkingAsymmetryPercentage")
                            Text("• HKQuantityTypeIdentifierWalkingDoubleSupportPercentage")
                        }
                        .font(.caption)
                        .foregroundColor(.secondary)
                    }
                }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Save") {
                        saveSettings()
                        dismiss()
                    }
                }
            }
        }
        .onAppear {
            tempServerURL = dataTransmitter.serverURL
        }
    }
    
    private func saveSettings() {
        dataTransmitter.serverURL = tempServerURL
        // Save other settings to UserDefaults
        UserDefaults.standard.set(updateInterval, forKey: "updateInterval")
        UserDefaults.standard.set(dataRetentionDays, forKey: "dataRetentionDays")
        UserDefaults.standard.set(enableNotifications, forKey: "enableNotifications")
    }
    
    private func testConnection() {
        // Implement connection test
        print("Testing connection to: \(tempServerURL)")
    }
}

// MARK: - Alternative HTTP REST API Implementation
extension DataTransmitter {
    func sendDataViaHTTP(_ gaitData: GaitData, patientID: String) {
        // For integration with your existing Python backend
        guard let url = URL(string: "https://your-api.com/ms-gait-data") else { return }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer YOUR_API_KEY", forHTTPHeaderField: "Authorization")
        
        var dataDict = gaitData.dictionary
        dataDict["patient_id"] = patientID
        
        do {
            request.httpBody = try JSONSerialization.data(withJSONObject: dataDict)
            
            URLSession.shared.dataTask(with: request) { data, response, error in
                if let error = error {
                    print("HTTP send error: \(error)")
                    return
                }
                
                if let httpResponse = response as? HTTPURLResponse {
                    print("HTTP Status: \(httpResponse.statusCode)")
                    if httpResponse.statusCode == 200 {
                        print("Gait data successfully sent to Python backend")
                    }
                }
            }.resume()
            
        } catch {
            print("Encoding error: \(error)")
        }
    }
    
    func sendBatchDataForPythonAnalysis(_ historicalData: [GaitData], patientID: String) {
        // Format data exactly like your Python script expects
        let records = historicalData.map { gaitData -> [String: Any] in
            let formatter = DateFormatter()
            formatter.dateFormat = "yyyy-MM-dd HH:mm:ss Z" // Apple Health XML format
            
            return [
                "type": "HKQuantityTypeIdentifierWalkingSpeed",
                "startDate": formatter.string(from: gaitData.timestamp),
                "value": String(gaitData.walkingSpeed ?? 0),
                "unit": "m/s"
            ]
            // Add other metrics as separate records to match XML structure
        }
        
        let payload = [
            "patient_id": patientID,
            "records": records,
            "export_date": ISO8601DateFormatter().string(from: Date())
        ] as [String : Any]
        
        guard let url = URL(string: "https://your-api.com/bulk-gait-data") else { return }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        do {
            request.httpBody = try JSONSerialization.data(withJSONObject: payload)
            
            URLSession.shared.dataTask(with: request) { data, response, error in
                if let error = error {
                    print("Batch upload error: \(error)")
                    return
                }
                
                print("Historical data batch uploaded successfully")
            }.resume()
            
        } catch {
            print("Batch encoding error: \(error)")
        }
    }
}
