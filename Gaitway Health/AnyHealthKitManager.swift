//
//  AnyHealthKitManager.swift
//  Gaitway Health
//
//  Created by Noval, Cameron on 9/1/25.
//


import Foundation
import HealthKit

class AnyHealthKitManager: ObservableObject, HealthKitManaging {
    private let _requestAuthorization: () -> Void
    private let _startRealTimeMonitoring: (@escaping (GaitData) -> Void) -> Void
    private let _stopRealTimeMonitoring: () -> Void
    private let _fetchHistoricalGaitData: (@escaping ([GaitData]) -> Void) -> Void
    private let _exportToXML: (String, @escaping (Bool) -> Void) -> Void

    init<T: ObservableObject & HealthKitManaging>(_ base: T) {
        _requestAuthorization = base.requestAuthorization
        _startRealTimeMonitoring = base.startRealTimeMonitoring
        _stopRealTimeMonitoring = base.stopRealTimeMonitoring
        _fetchHistoricalGaitData = base.fetchHistoricalGaitData
        _exportToXML = base.exportToXML
    }

    func requestAuthorization() { _requestAuthorization() }
    func startRealTimeMonitoring(callback: @escaping (GaitData) -> Void) { _startRealTimeMonitoring(callback) }
    func stopRealTimeMonitoring() { _stopRealTimeMonitoring() }
    func fetchHistoricalGaitData(completion: @escaping ([GaitData]) -> Void) { _fetchHistoricalGaitData(completion) }
    func exportToXML(patientID: String, completion: @escaping (Bool) -> Void) { _exportToXML(patientID, completion) }
}
