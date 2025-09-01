//
//  HealthKitService.swift
//  Gaitway Health
//
//  Created by Noval, Cameron on 9/1/25.
//

import Foundation

// MARK: - Mode Selector
enum HealthKitMode {
    case real
    case mock
}

// MARK: - Service
class HealthKitService {
    // Flip this flag to swap between real HealthKit and mock data
    static var mode: HealthKitMode = .mock

    // Shared instance returned as a type-erased AnyHealthKitManager
    static var shared: AnyHealthKitManager {
        switch mode {
        case .real:
            return AnyHealthKitManager(HealthKitManager())
        case .mock:
            return AnyHealthKitManager(MockHealthKitManager())
        }
    }
}
