//
//  MockHealthKitManager 2.swift
//  Gaitway Health
//
//  Created by Noval, Cameron on 9/1/25.
//


import Foundation
import HealthKit
import HealthKit

protocol HealthKitManaging {
    func requestAuthorization()
    func startRealTimeMonitoring(callback: @escaping (GaitData) -> Void)
    func stopRealTimeMonitoring()
    func fetchHistoricalGaitData(completion: @escaping ([GaitData]) -> Void)
    func exportToXML(patientID: String, completion: @escaping (Bool) -> Void)
}

// MARK: - Enhanced Mock HealthKit Manager
class MockHealthKitManager: ObservableObject, HealthKitManaging {
    private var gaitDataCallback: ((GaitData) -> Void)?
    private var timer: Timer?

    func requestAuthorization() {
        print("Mock: Authorization granted automatically")
    }

    func startRealTimeMonitoring(callback: @escaping (GaitData) -> Void) {
        gaitDataCallback = callback
        timer = Timer.scheduledTimer(withTimeInterval: 5.0, repeats: true) { _ in
            let mockData = GaitData(
                timestamp: Date(),
                walkingSpeed: Double.random(in: 0.6...1.4),
                stepLength: Double.random(in: 0.5...0.8),
                walkingAsymmetry: Double.random(in: 0...15),
                doubleSupportTime: Double.random(in: 20...40),
                stepCount: Int.random(in: 50...200),
                stepCadence: Double.random(in: 80...120),
                sixMinuteWalkDistance: Double.random(in: 300...500)
            )
            callback(mockData)
        }
    }

    func stopRealTimeMonitoring() {
        timer?.invalidate()
        timer = nil
        gaitDataCallback = nil
    }

    func fetchHistoricalGaitData(completion: @escaping ([GaitData]) -> Void) {
        let history = (1...30).map { day -> GaitData in
            let date = Calendar.current.date(byAdding: .day, value: -day, to: Date())!
            return GaitData(
                timestamp: date,
                walkingSpeed: Double.random(in: 0.6...1.4),
                stepLength: Double.random(in: 0.5...0.8),
                walkingAsymmetry: Double.random(in: 0...15),
                doubleSupportTime: Double.random(in: 20...40),
                stepCount: Int.random(in: 500...2000),
                stepCadence: Double.random(in: 80...120),
                sixMinuteWalkDistance: Double.random(in: 300...500)
            )
        }
        completion(history)
    }

    func exportToXML(patientID: String, completion: @escaping (Bool) -> Void) {
        print("Mock: Export to XML for patient \(patientID)")
        completion(true)
    }
}
